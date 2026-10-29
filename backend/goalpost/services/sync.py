"""The sync runtime: load cursor → fetch → validate → dedupe → local_date → save → cursor → SyncRun.

Connectors only fetch. Retries, waiting, pausing, validation and dedup all happen here.
"""

import logging
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from goalpost import sdk
from goalpost.models import Connector, Event, SyncRun
from goalpost.models.enums import SyncStatus, SyncTrigger
from goalpost.sdk.loader import Registry
from goalpost.services.connectors import read_env, resolve_secrets
from goalpost.services.dates import local_date
from goalpost.services.settings import ensure_settings

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0  # TransientError waits 2 s, then 8 s
MAX_WAIT_SECONDS = 60.0  # cap on a RateLimited wait, so a sync never stalls for long

Sleep = Callable[[float], None]

# One sync per connector at a time, across the scheduler and "Sync now".
_running: set[str] = set()
_running_lock = threading.Lock()


def _claim(connector_id: str) -> bool:
    with _running_lock:
        if connector_id in _running:
            return False
        _running.add(connector_id)
        return True


def _release(connector_id: str) -> None:
    with _running_lock:
        _running.discard(connector_id)


def validate_events(
    manifest: sdk.Manifest, events: Iterable[sdk.Event]
) -> tuple[list[tuple[sdk.Event, dict[str, Any]]], list[str]]:
    """Check each event against its declared kind and payload schema.

    Returns (valid events with normalized payloads, reasons for rejected events).
    """
    valid: list[tuple[sdk.Event, dict[str, Any]]] = []
    rejected: list[str] = []
    for event in events:
        kind = manifest.event_kind(event.kind)
        if kind is None:
            rejected.append(f"{event.source_id}: unknown kind {event.kind!r}")
            continue
        try:
            payload = kind.payload.model_validate(event.payload).model_dump(mode="json")
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first["loc"]) or "payload"
            rejected.append(f"{event.source_id}: {where}: {first['msg']}")
            continue
        valid.append((event, payload))
    return valid, rejected


def store_events(
    session: Session,
    connector: Connector,
    manifest: sdk.Manifest,
    events: Iterable[sdk.Event],
    timezone: str,
) -> tuple[int, list[str]]:
    """Validate, dedupe by (connector, source_id) and save. Returns (events added, rejections)."""
    valid, rejected = validate_events(manifest, events)
    unique: dict[str, tuple[sdk.Event, dict[str, Any]]] = {}
    for event, payload in sorted(valid, key=lambda pair: pair[0].occurred_at):
        unique.setdefault(event.source_id, (event, payload))
    existing = set(
        session.scalars(
            select(Event.source_id).where(
                Event.connector_id == connector.id, Event.source_id.in_(list(unique))
            )
        )
    )
    added = 0
    for source_id, (event, payload) in unique.items():
        if source_id in existing:
            continue
        session.add(
            Event(
                connector_id=connector.id,
                source_id=source_id,
                kind=event.kind,
                occurred_at=event.occurred_at,
                # Credit goes to the day it happened in the user's timezone, not when it synced.
                local_date=local_date(event.occurred_at, timezone),
                payload=payload,
            )
        )
        added += 1
    session.flush()
    return added, rejected


def _fetch_with_retries(
    connector: sdk.Connector[Any],
    config: Any,
    secrets: Mapping[str, str],
    cursor: dict[str, Any] | None,
    sleep: Sleep,
) -> tuple[sdk.FetchResult, SyncStatus, str | None]:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return connector.fetch(config, secrets, cursor), SyncStatus.OK, None
        except sdk.PartialResult as exc:
            return exc.result, SyncStatus.PARTIAL, str(exc)
        except sdk.RateLimited as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            sleep(min(max(exc.retry_after, 0.0), MAX_WAIT_SECONDS))
        except sdk.TransientError:
            if attempt == MAX_ATTEMPTS:
                raise
            sleep(BACKOFF_SECONDS * 4 ** (attempt - 1))
    raise AssertionError("unreachable")


def sync_connector(
    session: Session,
    connector: Connector,
    trigger: SyncTrigger,
    registry: Registry,
    *,
    env: Mapping[str, str] | None = None,
    sleep: Sleep = time.sleep,
) -> SyncRun | None:
    """Sync one connector and record a SyncRun. Returns None if it is already syncing."""
    if not _claim(connector.id):
        return None
    try:
        return _sync(session, connector, trigger, registry, env, sleep)
    finally:
        _release(connector.id)


def _sync(
    session: Session,
    connector: Connector,
    trigger: SyncTrigger,
    registry: Registry,
    env: Mapping[str, str] | None,
    sleep: Sleep,
) -> SyncRun:
    run = SyncRun(connector_id=connector.id, trigger=trigger, started_at=datetime.now(UTC))
    session.add(run)
    session.commit()  # visible as "syncing" while it runs

    status, error, added = SyncStatus.FAILED, None, 0
    try:
        cls = registry.get(connector.type)
        if cls is None:
            raise sdk.ConnectorError(f"Connector type {connector.type!r} isn't installed")
        manifest = cls.manifest
        try:
            config = manifest.config.model_validate(connector.config)
        except ValidationError as exc:
            raise sdk.ConnectorError(f"Config is invalid: {exc.errors()[0]['msg']}") from exc
        secrets = resolve_secrets(
            manifest, connector.secret_ref, read_env() if env is None else env
        )

        result, status, error = _fetch_with_retries(cls(), config, secrets, connector.cursor, sleep)

        timezone = ensure_settings(session).timezone
        added, rejected = store_events(session, connector, manifest, result.events, timezone)
        if rejected:
            status = SyncStatus.PARTIAL
            note = f"{len(rejected)} event(s) rejected, e.g. {rejected[0]}"
            error = f"{error}; {note}" if error else note
            log.warning("Connector %s rejected events: %s", connector.id, rejected)
        # The cursor moves only once the events it covers are saved.
        if result.cursor is not None:
            connector.cursor = result.cursor
        if status == SyncStatus.OK:
            connector.pause_reason = None
    except sdk.AuthError as exc:
        session.rollback()
        status, error, added = SyncStatus.FAILED, str(exc), 0
        connector.pause_reason = str(exc)
    except sdk.ConnectorError as exc:
        session.rollback()
        status, error, added = SyncStatus.FAILED, str(exc), 0
    except Exception as exc:  # a connector bug must never take the scheduler down
        session.rollback()
        log.exception("Sync failed for connector %s", connector.id)
        status, error, added = SyncStatus.FAILED, f"Unexpected error: {exc}", 0

    run.status = status
    run.error = error
    run.events_added = added
    run.finished_at = datetime.now(UTC)
    session.commit()
    # M4: run the rule engine over the new events here.
    return run


def _ran_recently(session: Session, connector: Connector, registry: Registry) -> bool:
    cls = registry.get(connector.type)
    if cls is None:
        return False
    since = datetime.now(UTC) - cls.manifest.sync_hints.min_interval
    last_ok = session.scalar(
        select(SyncRun.started_at)
        .where(
            SyncRun.connector_id == connector.id,
            SyncRun.status.in_([SyncStatus.OK, SyncStatus.PARTIAL]),
        )
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    return last_ok is not None and last_ok > since


def sync_connectors(
    factory: sessionmaker[Session],
    registry: Registry,
    trigger: SyncTrigger,
    connector_ids: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    sleep: Sleep = time.sleep,
) -> list[SyncRun]:
    """Sync enabled connectors (or the given ones).

    Scheduled and startup syncs skip paused connectors and respect each connector's minimum
    interval. A manual "Sync now" always runs, and a successful run lifts an auth pause.
    """
    runs: list[SyncRun] = []
    with factory() as session:
        query = select(Connector).where(Connector.enabled.is_(True)).order_by(Connector.id)
        if connector_ids is not None:
            query = query.where(Connector.id.in_(connector_ids))
        for connector in session.scalars(query).all():
            if trigger != SyncTrigger.MANUAL and (
                connector.pause_reason or _ran_recently(session, connector, registry)
            ):
                continue
            run = sync_connector(session, connector, trigger, registry, env=env, sleep=sleep)
            if run is not None:
                runs.append(run)
    return runs


def fail_interrupted_runs(session: Session) -> int:
    """Close runs left open by a crash or restart, so nothing shows as syncing forever."""
    stuck = session.scalars(select(SyncRun).where(SyncRun.finished_at.is_(None))).all()
    for run in stuck:
        run.status = SyncStatus.FAILED
        run.error = "Interrupted: the app stopped before this sync finished"
        run.finished_at = datetime.now(UTC)
    session.commit()
    return len(stuck)
