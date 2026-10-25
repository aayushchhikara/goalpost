import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from goalpost.db import Base
from goalpost.models.base import IdMixin, UserMixin, UTCDateTime, str_enum, utcnow
from goalpost.models.enums import (
    EvidenceAddedBy,
    SuggestionSource,
    SuggestionStatus,
    SyncStatus,
    SyncTrigger,
)


class Connector(IdMixin, UserMixin, Base):
    __tablename__ = "connectors"

    type: Mapped[str] = mapped_column(String(64))  # matches the SDK manifest id
    name: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Name of the .env key holding the secret; the secret itself never enters the DB.
    secret_ref: Mapped[str | None] = mapped_column(String(128))
    cursor: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SyncRun(IdMixin, UserMixin, Base):
    __tablename__ = "sync_runs"

    connector_id: Mapped[str] = mapped_column(ForeignKey("connectors.id"), index=True)
    trigger: Mapped[SyncTrigger] = mapped_column(str_enum(SyncTrigger))
    started_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime())
    # Null while the run is in progress.
    status: Mapped[SyncStatus | None] = mapped_column(str_enum(SyncStatus))
    events_added: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Event(IdMixin, UserMixin, Base):
    """An immutable fact from a connector. Append-only."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("connector_id", "source_id"),)

    connector_id: Mapped[str] = mapped_column(ForeignKey("connectors.id"))
    source_id: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[dt.datetime] = mapped_column(UTCDateTime())
    # The day in the user's timezone at ingestion; decides daily credit.
    local_date: Mapped[dt.date] = mapped_column(Date, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Rule(IdMixin, UserMixin, Base):
    __tablename__ = "rules"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), unique=True)
    connector_type: Mapped[str] = mapped_column(String(64))
    condition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Suggestion(IdMixin, UserMixin, Base):
    __tablename__ = "suggestions"

    occurrence_id: Mapped[str] = mapped_column(ForeignKey("occurrences.id"), index=True)
    source: Mapped[SuggestionSource] = mapped_column(str_enum(SuggestionSource))
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("rules.id", ondelete="SET NULL"))
    confidence: Mapped[float | None] = mapped_column(Float)  # AI suggestions only
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SuggestionStatus] = mapped_column(
        str_enum(SuggestionStatus), default=SuggestionStatus.PENDING
    )
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime())


class RuleExclusion(IdMixin, UserMixin, Base):
    """A filter learned from a rejected suggestion (or added by hand)."""

    __tablename__ = "rule_exclusions"

    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), index=True)
    filter: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_from_suggestion_id: Mapped[str | None] = mapped_column(
        ForeignKey("suggestions.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SuggestionEvent(UserMixin, Base):
    __tablename__ = "suggestion_events"

    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("suggestions.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)


class Evidence(UserMixin, Base):
    """An event attached to a done occurrence. One event can prove several occurrences."""

    __tablename__ = "evidence"

    occurrence_id: Mapped[str] = mapped_column(ForeignKey("occurrences.id"), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)
    added_by: Mapped[EvidenceAddedBy] = mapped_column(str_enum(EvidenceAddedBy))
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)
