"""Screen payloads: week, today, backlog and the task drawer. Derived views, computed on read."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from goalpost.models import Occurrence, Task, Week
from goalpost.models.enums import OccurrenceStatus, Priority, TaskKind, TaskStatus
from goalpost.schemas.planning import (
    Adherence,
    BacklogItem,
    BacklogResponse,
    OccurrenceRead,
    Tally,
    TaskDetailResponse,
    TaskRead,
    TodayResponse,
    WeekDay,
    WeekResponse,
)
from goalpost.services.dates import week_monday
from goalpost.services.planning import check_monday, find_week, status_for_week, week_end

PRIORITY_RANK = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def week_view(session: Session, monday: date, today: date) -> WeekResponse:
    check_monday(monday)
    week = find_week(session, monday)
    occurrences = _week_occurrences(session, week)
    by_day: dict[date, list[Occurrence]] = defaultdict(list)
    for occurrence in occurrences:
        if occurrence.date is not None:
            by_day[occurrence.date].append(occurrence)
    days = [monday + timedelta(days=i) for i in range(7)]
    return WeekResponse(
        week_start=monday,
        week_end=week_end(monday),
        iso_week=monday.isocalendar().week,
        status=week.status if week else status_for_week(monday, today),
        days=[WeekDay(date=d, occurrences=_read(_sorted(by_day[d]))) for d in days],
        any_day=_read(_sorted([o for o in occurrences if o.date is None], pending_first=True)),
        adherence=_adherence(occurrences),
        summary=_tally(occurrences),
    )


def today_view(session: Session, today: date) -> TodayResponse:
    monday = week_monday(today)
    occurrences = _week_occurrences(session, find_week(session, monday))
    return TodayResponse(
        date=today,
        week_start=monday,
        iso_week=monday.isocalendar().week,
        items=_read(_sorted([o for o in occurrences if o.date == today], pending_first=True)),
        any_day=_read(_sorted([o for o in occurrences if o.date is None], pending_first=True)),
        adherence=_adherence(occurrences),
        summary=_tally(occurrences),
    )


def backlog_view(session: Session, priority: Priority | None = None) -> BacklogResponse:
    query = select(Task).where(
        Task.kind == TaskKind.ONE_OFF, Task.status == TaskStatus.OPEN, Task.in_backlog.is_(True)
    )
    if priority is not None:
        query = query.where(Task.priority == priority)
    tasks = sorted(session.scalars(query), key=lambda t: (PRIORITY_RANK[t.priority], t.created_at))

    history = session.execute(
        select(
            Occurrence.task_id,
            func.max(Week.start_date),
            func.count(func.distinct(Occurrence.week_id)),
        )
        .join(Week, Occurrence.week_id == Week.id)
        .where(Occurrence.task_id.in_([t.id for t in tasks]))
        .group_by(Occurrence.task_id)
    ).all()
    last_week = {task_id: (last, attempts) for task_id, last, attempts in history}
    return BacklogResponse(
        items=[
            BacklogItem(
                task=TaskRead.model_validate(t),
                last_planned_week_start=last_week.get(t.id, (None, 0))[0],
                attempts=last_week.get(t.id, (None, 0))[1],
            )
            for t in tasks
        ]
    )


def task_detail(session: Session, task: Task, today: date) -> TaskDetailResponse:
    occurrences = list(session.scalars(select(Occurrence).where(Occurrence.task_id == task.id)))
    history = sorted(
        occurrences, key=lambda o: (o.week_start, o.date or week_end(o.week_start)), reverse=True
    )
    monday = week_monday(today)
    this_week = sorted(
        (o for o in occurrences if o.week_start == monday), key=lambda o: o.date or week_end(monday)
    )
    # Today's occurrence, else the next pending one this week, else whatever this week holds.
    current = (
        next((o for o in this_week if o.date == today), None)
        or next((o for o in this_week if o.status == OccurrenceStatus.PENDING), None)
        or (this_week[0] if this_week else None)
    )
    return TaskDetailResponse(
        task=TaskRead.model_validate(task),
        current_occurrence=OccurrenceRead.model_validate(current) if current else None,
        history=_read(history),
    )


def _week_occurrences(session: Session, week: Week | None) -> list[Occurrence]:
    if week is None:
        return []
    return list(session.scalars(select(Occurrence).where(Occurrence.week_id == week.id)))


def _sorted(occurrences: Sequence[Occurrence], pending_first: bool = False) -> list[Occurrence]:
    def key(o: Occurrence) -> tuple[bool, int, object]:
        waiting = o.status in (OccurrenceStatus.PENDING, OccurrenceStatus.MISSED)
        return (pending_first and not waiting, PRIORITY_RANK[o.task.priority], o.task.created_at)

    return sorted(occurrences, key=key)


def _read(occurrences: Sequence[Occurrence]) -> list[OccurrenceRead]:
    return [OccurrenceRead.model_validate(o) for o in occurrences]


def _counts(occurrences: Sequence[Occurrence]) -> dict[str, int | float | None]:
    statuses = Counter(o.status for o in occurrences)
    planned = len(occurrences)
    done = statuses[OccurrenceStatus.DONE]
    skipped = statuses[OccurrenceStatus.SKIPPED]
    # Weekly adherence = done ÷ (planned − skipped).
    counted = planned - skipped
    return {
        "planned": planned,
        "done": done,
        "late": sum(1 for o in occurrences if o.status == OccurrenceStatus.DONE and o.late),
        "skipped": skipped,
        "missed": statuses[OccurrenceStatus.MISSED],
        "pending": statuses[OccurrenceStatus.PENDING],
        "rate": done / counted if counted else None,
    }


def _tally(occurrences: Sequence[Occurrence]) -> Tally:
    return Tally.model_validate(_counts(occurrences))


def _adherence(occurrences: Sequence[Occurrence]) -> list[Adherence]:
    by_task: dict[str, list[Occurrence]] = defaultdict(list)
    for occurrence in occurrences:
        if occurrence.task.kind == TaskKind.RECURRING:
            by_task[occurrence.task_id].append(occurrence)
    tasks = sorted(
        (group[0].task for group in by_task.values()),
        key=lambda t: (PRIORITY_RANK[t.priority], t.created_at),
    )
    return [
        Adherence.model_validate({"task_id": t.id, "title": t.title, **_counts(by_task[t.id])})
        for t in tasks
    ]
