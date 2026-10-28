from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from alembic import command
from goalpost.db import make_engine
from goalpost.migrate import alembic_config
from goalpost.models import Connector, Event, Occurrence, Task
from goalpost.models.enums import TaskKind
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

MVP_TABLES = {
    "settings",
    "weeks",
    "tasks",
    "occurrences",
    "connectors",
    "sync_runs",
    "events",
    "rules",
    "rule_exclusions",
    "suggestions",
    "suggestion_events",
    "evidence",
}


def _tables(url: str) -> set[str]:
    engine = make_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migration_creates_every_table_on_an_empty_database(db_url: str) -> None:
    engine = make_engine(db_url)
    inspector = inspect(engine)
    assert MVP_TABLES <= set(inspector.get_table_names())
    for table in MVP_TABLES:
        assert "user_id" in {c["name"] for c in inspector.get_columns(table)}, table
    engine.dispose()


def test_models_match_migrations(db_url: str) -> None:
    command.check(alembic_config(db_url))  # raises if autogenerate would find changes


def test_downgrade_and_upgrade_again(db_url: str) -> None:
    cfg = alembic_config(db_url)
    command.downgrade(cfg, "0001")
    assert not MVP_TABLES & _tables(db_url)
    command.upgrade(cfg, "head")
    assert MVP_TABLES <= _tables(db_url)


def _connector(session: Session) -> Connector:
    connector = Connector(type="leetcode", name="LeetCode")
    session.add(connector)
    session.flush()
    return connector


def _event(connector: Connector, source_id: str) -> Event:
    return Event(
        connector_id=connector.id,
        source_id=source_id,
        kind="submission",
        occurred_at=datetime(2026, 10, 26, 18, 20, tzinfo=UTC),
        local_date=date(2026, 10, 26),
    )


def test_events_are_unique_per_connector_and_source_id(db_session: Session) -> None:
    github = _connector(db_session)
    other = _connector(db_session)
    db_session.add_all([_event(github, "abc123"), _event(other, "abc123")])
    db_session.commit()

    db_session.add(_event(github, "abc123"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_foreign_keys_are_enforced(db_session: Session) -> None:
    db_session.add(Occurrence(task_id="missing-task", week_id="missing-week"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_timestamps_come_back_as_aware_utc(db_session: Session) -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    connector = _connector(db_session)
    event = _event(connector, "s1")
    event.occurred_at = datetime(2026, 10, 26, 23, 50, tzinfo=ist)
    db_session.add(event)
    db_session.commit()
    db_session.expunge_all()

    stored = db_session.scalars(select(Event)).one()
    assert stored.occurred_at == datetime(2026, 10, 26, 18, 20, tzinfo=UTC)
    assert stored.occurred_at.tzinfo is UTC


def test_naive_timestamps_are_rejected(db_session: Session) -> None:
    connector = _connector(db_session)
    event = _event(connector, "s1")
    event.occurred_at = datetime(2026, 10, 26, 18, 20)
    db_session.add(event)
    with pytest.raises(StatementError, match="naive"):
        db_session.commit()


def test_rows_get_ulid_ids_and_the_default_user(db_session: Session) -> None:
    task = Task(title="LeetCode daily", kind=TaskKind.RECURRING, recurrence_days=47)
    db_session.add(task)
    db_session.commit()
    assert len(task.id) == 26
    assert task.user_id == "local"
    assert task.in_backlog is True
    assert task.created_at.tzinfo is UTC
