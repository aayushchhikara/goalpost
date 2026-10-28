import datetime as dt
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from goalpost.models.enums import OccurrenceStatus, Priority, TaskKind, TaskStatus, WeekStatus
from goalpost.services.dates import decode_days

# Weekdays as in date.weekday(): Monday = 0 … Sunday = 6.
Weekday = Annotated[int, Field(ge=0, le=6)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


def _decode_mask(value: Any) -> Any:
    return decode_days(value) if isinstance(value, int) else value


# Requests


class PlanTarget(BaseModel):
    week_start: dt.date = Field(description="Monday of the week to plan into")
    date: dt.date | None = Field(
        default=None, description="A day in that week, or null for any day (one-off only)"
    )


class TaskCreate(BaseModel):
    title: Title
    notes: str = ""
    kind: TaskKind = TaskKind.ONE_OFF
    priority: Priority = Priority.MEDIUM
    recurrence_days: list[Weekday] | None = Field(default=None, description="Recurring only")
    plan: PlanTarget | None = Field(
        default=None, description="Plan straight into a week; otherwise one-offs go to the backlog"
    )

    @model_validator(mode="after")
    def _days_match_kind(self) -> Self:
        if self.kind == TaskKind.RECURRING and not self.recurrence_days:
            raise ValueError("recurring tasks need at least one recurrence day")
        if self.kind == TaskKind.ONE_OFF and self.recurrence_days:
            raise ValueError("one-off tasks have no recurrence days")
        return self


class TaskUpdate(BaseModel):
    """Fields left out stay as they are."""

    title: Title | None = None
    notes: str | None = None
    priority: Priority | None = None
    recurrence_days: list[Weekday] | None = Field(
        default=None, min_length=1, description="Recurring only; applies to remaining days"
    )


class PlanItem(BaseModel):
    task_id: str
    date: dt.date | None = Field(
        default=None,
        description="A day in the week, or null for any day; recurring tasks use their days",
    )


class PlanWeekRequest(BaseModel):
    items: list[PlanItem] = []


class OccurrenceUpdate(BaseModel):
    date: dt.date | None = Field(description="New day in the same week, or null for any day")


# Responses


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    notes: str
    kind: TaskKind
    priority: Priority
    recurrence_days: list[int] | None
    in_backlog: bool
    status: TaskStatus
    first_planned_week_start: dt.date | None
    created_at: dt.datetime

    _decode_days = field_validator("recurrence_days", mode="before")(_decode_mask)


class TaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    kind: TaskKind
    priority: Priority
    recurrence_days: list[int] | None

    _decode_days = field_validator("recurrence_days", mode="before")(_decode_mask)


class OccurrenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task: TaskSummary
    week_start: dt.date
    date: dt.date | None = Field(description="Null means any day this week")
    status: OccurrenceStatus
    late: bool
    completed_at: dt.datetime | None
    carried_over: bool


class Tally(BaseModel):
    planned: int
    done: int
    late: int
    skipped: int
    missed: int
    pending: int
    rate: float | None = Field(description="done / (planned - skipped); null when nothing counts")


class Adherence(Tally):
    task_id: str
    title: str


class WeekDay(BaseModel):
    date: dt.date
    occurrences: list[OccurrenceRead]


class WeekResponse(BaseModel):
    week_start: dt.date
    week_end: dt.date
    iso_week: int
    status: WeekStatus
    days: list[WeekDay]
    any_day: list[OccurrenceRead]
    adherence: list[Adherence] = Field(description="Recurring tasks only")
    summary: Tally


class TodayResponse(BaseModel):
    date: dt.date
    week_start: dt.date
    iso_week: int
    items: list[OccurrenceRead] = Field(description="Occurrences dated today")
    any_day: list[OccurrenceRead] = Field(description="This week's any-day occurrences")
    adherence: list[Adherence]
    summary: Tally


class BacklogItem(BaseModel):
    task: TaskRead
    last_planned_week_start: dt.date | None
    attempts: int = Field(description="Weeks the task was planned into")


class BacklogResponse(BaseModel):
    items: list[BacklogItem]


class TaskDetailResponse(BaseModel):
    task: TaskRead
    current_occurrence: OccurrenceRead | None = Field(description="This week's occurrence, if any")
    history: list[OccurrenceRead] = Field(description="Every occurrence, newest week first")


class CloseResult(BaseModel):
    activated_weeks: list[dt.date]
    closed_weeks: list[dt.date]
    missed: int
    returned_to_backlog: int
