"""Installed connector types, connector instances, secrets and the Test button. Callers commit."""

import logging
import os
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from typing import Any

from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from goalpost.errors import Invalid, NotFound
from goalpost.models import Connector, SyncRun
from goalpost.models.enums import SyncStatus
from goalpost.schemas.connectors import (
    ConnectorCreate,
    ConnectorLoadProblem,
    ConnectorRead,
    ConnectorStatus,
    ConnectorTestResult,
    ConnectorTypeRead,
    ConnectorTypesResponse,
    EventKindRead,
    SecretRequirement,
    SyncRunRead,
)
from goalpost.sdk import AuthError, ConnectorError, Manifest
from goalpost.sdk.loader import Registry, discover
from goalpost.settings import REPO_ROOT, get_settings

log = logging.getLogger(__name__)


@lru_cache
def installed_connectors() -> Registry:
    return discover(get_settings().connectors_dir)


# Secrets live only in .env or the environment, never in the database.


def read_env() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(REPO_ROOT / ".env").items() if v}
    values.update({k: v for k, v in os.environ.items() if v})
    return values


def secret_keys(manifest: Manifest, secret_ref: str | None) -> dict[str, str]:
    """Map each secret the connector asks for to the .env key that holds it."""
    if secret_ref and len(manifest.secrets) == 1:
        return {manifest.secrets[0]: secret_ref}
    return {name: name for name in manifest.secrets}


def resolve_secrets(
    manifest: Manifest, secret_ref: str | None, env: Mapping[str, str]
) -> dict[str, str]:
    secrets: dict[str, str] = {}
    for name, key in secret_keys(manifest, secret_ref).items():
        if not env.get(key):
            raise AuthError(f"{key} isn't set in .env")
        secrets[name] = env[key]
    return secrets


def parse_config(manifest: Manifest, config: dict[str, Any]) -> Any:
    try:
        return manifest.config.model_validate(config)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"])
        raise Invalid(f"{field}: {first['msg']}", field=f"config.{field}") from exc


# Connector types


def connector_types_view(registry: Registry, env: Mapping[str, str]) -> ConnectorTypesResponse:
    items = []
    for cls in sorted(registry.types.values(), key=lambda c: c.manifest.name):
        m = cls.manifest
        items.append(
            ConnectorTypeRead(
                id=m.id,
                name=m.name,
                version=m.version,
                description=m.description,
                icon=m.icon,
                auth=m.auth,
                config_schema=m.config.model_json_schema(),
                secrets=[SecretRequirement(name=s, present=bool(env.get(s))) for s in m.secrets],
                event_kinds=[
                    EventKindRead(
                        name=k.name,
                        description=k.description,
                        payload_schema=k.payload.model_json_schema(),
                        rule_fields=k.rule_fields,
                    )
                    for k in m.event_kinds
                ],
                min_sync_interval_minutes=int(m.sync_hints.min_interval.total_seconds() // 60),
                max_items=m.sync_hints.max_items,
                capabilities=m.capabilities,
            )
        )
    errors = [ConnectorLoadProblem(folder=f, message=msg) for f, msg in registry.errors.items()]
    return ConnectorTypesResponse(items=items, load_errors=errors)


# Connector instances


def get_connector(session: Session, connector_id: str) -> Connector:
    row = session.get(Connector, connector_id)
    if row is None:
        raise NotFound(f"Connector {connector_id} not found")
    return row


def create_connector(session: Session, registry: Registry, data: ConnectorCreate) -> Connector:
    cls = registry.get(data.type)
    if cls is None:
        raise Invalid(f"No connector type {data.type!r} is installed", field="type")
    manifest = cls.manifest
    if data.secret_ref and not manifest.secrets:
        raise Invalid(f"{manifest.name} doesn't use secrets", field="secret_ref")
    config = parse_config(manifest, data.config)
    row = Connector(
        type=manifest.id,
        name=(data.name or "").strip() or manifest.name,
        config=config.model_dump(mode="json"),
        secret_ref=data.secret_ref,
    )
    session.add(row)
    session.flush()
    return row


def test_connector(
    row: Connector, registry: Registry, env: Mapping[str, str]
) -> ConnectorTestResult:
    """Run the connector's test_connection. A passing test lifts an auth pause."""
    cls = registry.get(row.type)
    if cls is None:
        return ConnectorTestResult(ok=False, message=f"Connector type {row.type!r} isn't installed")
    try:
        config = cls.manifest.config.model_validate(row.config)
        secrets = resolve_secrets(cls.manifest, row.secret_ref, env)
        message = cls().test_connection(config, secrets)
    except ValidationError as exc:
        return ConnectorTestResult(ok=False, message=f"Config is invalid: {exc.errors()[0]['msg']}")
    except ConnectorError as exc:
        return ConnectorTestResult(ok=False, message=str(exc))
    except Exception as exc:  # a connector bug must not break the Test button
        log.exception("test_connection failed for connector %s", row.id)
        return ConnectorTestResult(ok=False, message=f"Unexpected error: {exc}")
    row.pause_reason = None
    return ConnectorTestResult(ok=True, message=message)


def _status(row: Connector, last: SyncRun | None) -> ConnectorStatus:
    if not row.enabled:
        return ConnectorStatus.DISABLED
    if row.pause_reason:
        return ConnectorStatus.PAUSED
    if last is None:
        return ConnectorStatus.NEVER_SYNCED
    if last.finished_at is None:
        return ConnectorStatus.SYNCING
    if last.status == SyncStatus.FAILED:
        return ConnectorStatus.FAILING
    return ConnectorStatus.OK


def last_success_at(session: Session, connector_id: str) -> datetime | None:
    return session.scalar(
        select(SyncRun.finished_at)
        .where(
            SyncRun.connector_id == connector_id,
            SyncRun.status.in_([SyncStatus.OK, SyncStatus.PARTIAL]),
        )
        .order_by(SyncRun.finished_at.desc())
        .limit(1)
    )


def connector_read(session: Session, row: Connector) -> ConnectorRead:
    last = session.scalar(
        select(SyncRun)
        .where(SyncRun.connector_id == row.id)
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(1)
    )
    return ConnectorRead(
        id=row.id,
        type=row.type,
        name=row.name,
        config=row.config,
        secret_ref=row.secret_ref,
        enabled=row.enabled,
        pause_reason=row.pause_reason,
        status=_status(row, last),
        last_run=SyncRunRead.model_validate(last) if last else None,
        last_success_at=last_success_at(session, row.id),
    )


def connectors_view(session: Session) -> list[ConnectorRead]:
    rows = session.scalars(select(Connector).order_by(Connector.name, Connector.id))
    return [connector_read(session, row) for row in rows]
