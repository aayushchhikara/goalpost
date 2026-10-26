import datetime as dt

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from goalpost.db import Base
from goalpost.models.base import DEFAULT_USER_ID, IdMixin, UserMixin, UTCDateTime, str_enum, utcnow
from goalpost.models.enums import OccurrenceStatus, Priority, TaskKind, TaskStatus, WeekStatus


class UserSettings(IdMixin, Base):
    """One row per user: timezone, week start, AI on or off. Seeded from .env on first startup."""

    __tablename__ = "settings"

    user_id: Mapped[str] = mapped_column(String(26), default=DEFAULT_USER_ID, unique=True)
    timezone: Mapped[str] = mapped_column(String(64))
    week_start: Mapped[str] = mapped_column(String(16), default="monday")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Week(IdMixin, UserMixin, Base):
    __tablename__ = "weeks"
    __table_args__ = (UniqueConstraint("user_id", "start_date"),)

    start_date: Mapped[dt.date] = mapped_column(Date)  # always a Monday
    status: Mapped[WeekStatus] = mapped_column(str_enum(WeekStatus), default=WeekStatus.PLANNING)


class Task(IdMixin, UserMixin, Base):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[TaskKind] = mapped_column(str_enum(TaskKind))
    priority: Mapped[Priority] = mapped_column(str_enum(Priority), default=Priority.MEDIUM)
    # Recurring only. Bit i set means weekday i (Monday = 0); see services.dates.
    recurrence_days: Mapped[int | None] = mapped_column(Integer)
    in_backlog: Mapped[bool] = mapped_column(Boolean, default=True)
    first_planned_week_id: Mapped[str | None] = mapped_column(ForeignKey("weeks.id"))
    status: Mapped[TaskStatus] = mapped_column(str_enum(TaskStatus), default=TaskStatus.OPEN)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)

    first_planned_week: Mapped[Week | None] = relationship(lazy="joined")

    @property
    def first_planned_week_start(self) -> dt.date | None:
        return self.first_planned_week.start_date if self.first_planned_week else None


class Occurrence(IdMixin, UserMixin, Base):
    __tablename__ = "occurrences"
    __table_args__ = (UniqueConstraint("task_id", "week_id", "date"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    week_id: Mapped[str] = mapped_column(ForeignKey("weeks.id"), index=True)
    # Null means "any day this week" (one-off only).
    date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[OccurrenceStatus] = mapped_column(
        str_enum(OccurrenceStatus), default=OccurrenceStatus.PENDING
    )
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime())

    task: Mapped[Task] = relationship(lazy="joined")
    week: Mapped[Week] = relationship(lazy="joined")

    @property
    def week_start(self) -> dt.date:
        return self.week.start_date

    @property
    def carried_over(self) -> bool:
        """True when a one-off task was first planned in an earlier week than this one."""
        return self.task.kind == TaskKind.ONE_OFF and self.task.first_planned_week_id not in (
            None,
            self.week_id,
        )
