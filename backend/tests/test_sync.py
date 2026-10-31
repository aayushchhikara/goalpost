from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from goalpost import sdk
from goalpost.models import Connector, Event, SyncRun, UserSettings
from goalpost.models.enums import SyncStatus, SyncTrigger
from goalpost.sdk.loader import Registry
from goalpost.services import sync
from goalpost.services.settings import ensure_settings
from goalpost.services.sync import fail_interrupted_runs, sync_connector, sync_connectors
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class FakeConfig(BaseModel):
    username: str


class Submission(BaseModel):
    problem: str
    status: str = "accepted"


class FakeConnector(sdk.Connector[FakeConfig]):
    """Each fetch takes the next scripted outcome: a FetchResult to return or an error to raise."""

    manifest = sdk.Manifest(
        id="fake",
        name="Fake",
        version="0.0.1",
        sdk_version=sdk.SDK_VERSION,
        config=FakeConfig,
        event_kinds=[sdk.EventKind(name="submission", payload=Submission, rule_fields=["status"])],
        sync_hints=sdk.SyncHints(min_interval=timedelta(hours=1)),
    )
    script: list[sdk.FetchResult | Exception] = []
    cursors_seen: list[dict[str, Any] | None] = []

    def test_connection(self, config: FakeConfig, secrets: Mapping[str, str]) -> str:
        return "ok"

    def fetch(
        self, config: FakeConfig, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> sdk.FetchResult:
        FakeConnector.cursors_seen.append(cursor)
        outcome = FakeConnector.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


REGISTRY = Registry(types={"fake": FakeConnector})
IST_2350_MONDAY = datetime(2026, 10, 26, 18, 20, tzinfo=UTC)  # 23:50 IST, Mon 26 Oct


def event(source_id: str, at: datetime = IST_2350_MONDAY, **payload: Any) -> sdk.Event:
    return sdk.Event(
        source_id=source_id,
        kind="submission",
        occurred_at=at,
        payload={"problem": "Two Sum", **payload},
    )


def result(*events: sdk.Event, cursor: dict[str, Any] | None = None) -> sdk.FetchResult:
    return sdk.FetchResult(events=list(events), cursor=cursor)


@pytest.fixture(autouse=True)
def reset_fake() -> None:
    FakeConnector.script = []
    FakeConnector.cursors_seen = []


@pytest.fixture
def connector(db_session: Session) -> Connector:
    settings = ensure_settings(db_session)
    settings.timezone = "Asia/Kolkata"
    row = Connector(type="fake", name="Fake", config={"username": "me"})
    db_session.add(row)
    db_session.commit()
    return row


def run(session: Session, row: Connector, sleeps: list[float] | None = None, **kw: Any) -> SyncRun:
    out = sync_connector(
        session,
        row,
        kw.pop("trigger", SyncTrigger.MANUAL),
        REGISTRY,
        env={},
        sleep=(sleeps if sleeps is not None else []).append,
        **kw,
    )
    assert out is not None
    return out


def events(session: Session) -> list[Event]:
    return list(session.scalars(select(Event).order_by(Event.occurred_at)))


def test_sync_saves_events_with_local_dates_and_the_cursor(
    db_session: Session, connector: Connector
) -> None:
    FakeConnector.script = [result(event("s1"), cursor={"last": 1})]
    sync_run = run(db_session, connector)

    assert (sync_run.status, sync_run.events_added, sync_run.error) == (SyncStatus.OK, 1, None)
    assert sync_run.finished_at is not None
    saved = events(db_session)
    assert [(e.source_id, e.kind, e.payload["problem"]) for e in saved] == [
        ("s1", "submission", "Two Sum")
    ]
    # 23:50 IST on Monday counts for Monday, though it's still Monday afternoon in UTC terms.
    assert saved[0].local_date == date(2026, 10, 26)
    assert saved[0].occurred_at == IST_2350_MONDAY
    assert connector.cursor == {"last": 1}


def test_a_second_sync_adds_nothing_new(db_session: Session, connector: Connector) -> None:
    FakeConnector.script = [
        result(event("s1"), event("s2"), cursor={"last": 2}),
        result(event("s2"), event("s2"), cursor={"last": 2}),  # overlap and an in-batch duplicate
    ]
    assert run(db_session, connector).events_added == 2
    second = run(db_session, connector)
    assert (second.status, second.events_added) == (SyncStatus.OK, 0)
    assert len(events(db_session)) == 2
    assert FakeConnector.cursors_seen == [None, {"last": 2}]


def test_invalid_events_are_rejected_and_the_rest_kept(
    db_session: Session, connector: Connector
) -> None:
    bad_kind = sdk.Event(source_id="s2", kind="commit", occurred_at=IST_2350_MONDAY, payload={})
    bad_payload = sdk.Event(
        source_id="s3", kind="submission", occurred_at=IST_2350_MONDAY, payload={}
    )
    FakeConnector.script = [result(event("s1"), bad_kind, bad_payload, cursor={"last": 3})]
    sync_run = run(db_session, connector)

    assert (sync_run.status, sync_run.events_added) == (SyncStatus.PARTIAL, 1)
    assert sync_run.error is not None and "2 event(s) rejected" in sync_run.error
    assert [e.source_id for e in events(db_session)] == ["s1"]


def test_auth_error_pauses_and_keeps_the_cursor(db_session: Session, connector: Connector) -> None:
    connector.cursor = {"last": 1}
    FakeConnector.script = [sdk.AuthError("token revoked")]
    sync_run = run(db_session, connector)

    assert (sync_run.status, sync_run.error) == (SyncStatus.FAILED, "token revoked")
    assert connector.pause_reason == "token revoked"
    assert connector.cursor == {"last": 1}


def test_paused_connectors_skip_scheduled_syncs_until_a_manual_one_succeeds(
    db_url: str, connector: Connector, db_session: Session
) -> None:
    connector.pause_reason = "token revoked"
    db_session.commit()
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)

    assert sync_connectors(factory, REGISTRY, SyncTrigger.SCHEDULE, env={}) == []

    FakeConnector.script = [result(event("s1"))]
    runs = sync_connectors(factory, REGISTRY, SyncTrigger.MANUAL, env={})
    assert [r.status for r in runs] == [SyncStatus.OK]
    db_session.expire_all()
    assert db_session.get(Connector, connector.id).pause_reason is None  # type: ignore[union-attr]


def test_rate_limits_wait_and_retry(db_session: Session, connector: Connector) -> None:
    FakeConnector.script = [
        sdk.RateLimited("slow down", retry_after=5),
        sdk.RateLimited("slow down", retry_after=600),
        result(event("s1")),
    ]
    sleeps: list[float] = []
    sync_run = run(db_session, connector, sleeps)
    assert (sync_run.status, sync_run.events_added) == (SyncStatus.OK, 1)
    assert sleeps == [5, sync.MAX_WAIT_SECONDS]  # a long Retry-After is capped


def test_transient_errors_back_off_then_fail_without_moving_the_cursor(
    db_session: Session, connector: Connector
) -> None:
    connector.cursor = {"last": 1}
    FakeConnector.script = [sdk.TransientError("timeout")] * 3
    sleeps: list[float] = []
    sync_run = run(db_session, connector, sleeps)

    assert (sync_run.status, sync_run.error) == (SyncStatus.FAILED, "timeout")
    assert sleeps == [2.0, 8.0]
    assert connector.cursor == {"last": 1}
    assert connector.pause_reason is None  # transient trouble doesn't pause
    assert events(db_session) == []


def test_partial_results_are_kept(db_session: Session, connector: Connector) -> None:
    FakeConnector.script = [
        sdk.PartialResult("page 2 failed", result(event("s1"), cursor={"last": 1}))
    ]
    sync_run = run(db_session, connector)
    assert (sync_run.status, sync_run.events_added, sync_run.error) == (
        SyncStatus.PARTIAL,
        1,
        "page 2 failed",
    )
    assert connector.cursor == {"last": 1}


def test_a_connector_bug_is_recorded_not_raised(db_session: Session, connector: Connector) -> None:
    FakeConnector.script = [KeyError("id")]
    sync_run = run(db_session, connector)
    assert sync_run.status == SyncStatus.FAILED
    assert sync_run.error == "Unexpected error: 'id'"


def test_missing_secret_pauses_with_a_readable_reason(db_session: Session) -> None:
    class Secretive(FakeConnector):
        manifest = FakeConnector.manifest.model_copy(
            update={"id": "secretive", "secrets": ["FAKE_TOKEN"]}
        )

    row = Connector(type="secretive", name="S", config={"username": "me"})
    db_session.add(row)
    db_session.commit()
    sync_run = sync_connector(
        db_session, row, SyncTrigger.MANUAL, Registry(types={"secretive": Secretive}), env={}
    )
    assert sync_run is not None and sync_run.status == SyncStatus.FAILED
    assert row.pause_reason == "FAKE_TOKEN isn't set in .env"


def test_uninstalled_type_fails_cleanly(db_session: Session) -> None:
    row = Connector(type="gone", name="Gone", config={})
    db_session.add(row)
    db_session.commit()
    sync_run = sync_connector(db_session, row, SyncTrigger.MANUAL, REGISTRY, env={})
    assert sync_run is not None
    assert (sync_run.status, sync_run.error) == (
        SyncStatus.FAILED,
        "Connector type 'gone' isn't installed",
    )


def test_scheduled_syncs_respect_the_minimum_interval(
    db_session: Session, connector: Connector
) -> None:
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)
    FakeConnector.script = [result(event("s1")), result(event("s2"))]
    assert len(sync_connectors(factory, REGISTRY, SyncTrigger.STARTUP, env={})) == 1
    assert sync_connectors(factory, REGISTRY, SyncTrigger.SCHEDULE, env={}) == []  # too soon
    assert len(sync_connectors(factory, REGISTRY, SyncTrigger.MANUAL, env={})) == 1  # "Sync now"


def test_one_sync_per_connector_at_a_time(db_session: Session, connector: Connector) -> None:
    assert sync._claim(connector.id)
    try:
        assert sync_connector(db_session, connector, SyncTrigger.MANUAL, REGISTRY, env={}) is None
    finally:
        sync._release(connector.id)


def test_interrupted_runs_are_closed_on_startup(db_session: Session, connector: Connector) -> None:
    db_session.add(SyncRun(connector_id=connector.id, trigger=SyncTrigger.SCHEDULE))
    db_session.commit()
    assert fail_interrupted_runs(db_session) == 1
    stuck = db_session.scalars(select(SyncRun)).one()
    assert stuck.status == SyncStatus.FAILED and stuck.finished_at is not None


def test_settings_timezone_drives_local_dates(db_session: Session, connector: Connector) -> None:
    settings = db_session.scalars(select(UserSettings)).one()
    settings.timezone = "UTC"
    db_session.commit()
    FakeConnector.script = [result(event("s1", at=datetime(2026, 10, 26, 18, 31, tzinfo=UTC)))]
    run(db_session, connector)
    assert events(db_session)[0].local_date == date(2026, 10, 26)
