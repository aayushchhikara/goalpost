"""Weeks, planning and the backlog flag. Callers commit; these functions only flush.

Rules that hold here: recurring days never roll over, one-off tasks live in at most one open
week at a time, and only the remaining days of a week (today onwards) are ever changed.
"""

from collections.abc import Iterable, Sequence
from datetime import date, timedelta

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from goalpost.errors import Conflict, Invalid, NotFound
from goalpost.models import Occurrence, Suggestion, Task, Week
from goalpost.models.enums import OccurrenceStatus, TaskKind, TaskStatus, WeekStatus
from goalpost.services.dates import decode_days


def week_end(monday: date) -> date:
    return monday + timedelta(days=6)


def status_for_week(monday: date, today: date) -> WeekStatus:
    if week_end(monday) < today:
        return WeekStatus.CLOSED
    if monday <= today:
        return WeekStatus.ACTIVE
    return WeekStatus.PLANNING


def check_monday(monday: date) -> None:
    if monday.weekday() != 0:
        raise Invalid(
            f"{monday} is not a Monday; weeks are addressed by their Monday", field="monday"
        )


def get_task(session: Session, task_id: str) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise NotFound(f"Task {task_id} not found")
    return task


def get_occurrence(session: Session, occurrence_id: str) -> Occurrence:
    occurrence = session.get(Occurrence, occurrence_id)
    if occurrence is None:
        raise NotFound(f"Occurrence {occurrence_id} not found")
    return occurrence


def find_week(session: Session, monday: date) -> Week | None:
    return session.scalar(select(Week).where(Week.start_date == monday))


def get_or_create_week(session: Session, monday: date, today: date) -> Week:
    """Weeks are created on first use."""
    check_monday(monday)
    week = find_week(session, monday)
    if week is None:
        week = Week(start_date=monday, status=status_for_week(monday, today))
        session.add(week)
        session.flush()
    return week


def check_day(week: Week, day: date, today: date) -> None:
    if not week.start_date <= day <= week_end(week.start_date):
        raise Invalid(f"{day} is not in the week of {week.start_date}", field="date")
    if day < today:
        raise Invalid(f"{day} has already passed", field="date")


def plan_week(
    session: Session, monday: date, items: Sequence[tuple[str, date | None]], today: date
) -> Week:
    """Plan tasks into a week, then generate occurrences for every open recurring task.

    Each item is (task_id, day); day is None for "any day" one-offs and for recurring tasks.
    """
    week = get_or_create_week(session, monday, today)
    if week.status == WeekStatus.CLOSED:
        raise Conflict(f"The week of {monday} is closed", code="week_closed")
    for task_id, day in items:
        plan_task(session, get_task(session, task_id), week, day, today)
    generate_recurring(session, week, today)
    return week


def plan_task(session: Session, task: Task, week: Week, day: date | None, today: date) -> None:
    if task.status != TaskStatus.OPEN:
        raise Conflict(
            f"Task is {task.status.value}; only open tasks can be planned", code="task_not_open"
        )
    if _occurrences_in(session, task, week):
        raise Conflict("Task is already planned into this week", code="already_planned")

    if task.kind == TaskKind.RECURRING:
        if day is not None:
            raise Invalid("Recurring tasks are planned on their recurrence days", field="date")
        add_recurring_days(session, task, week, today)
        return

    if day is not None:
        check_day(week, day, today)
    # A one-off lives in one open week at a time: planning it elsewhere moves a pending occurrence.
    delete_occurrences(session, _pending_in_open_weeks(session, task))
    session.add(Occurrence(task=task, week=week, date=day))
    task.in_backlog = False
    if task.first_planned_week_id is None:
        task.first_planned_week = week


def add_recurring_days(
    session: Session, task: Task, week: Week, today: date, existing: Iterable[date] = ()
) -> None:
    """Add an occurrence for each recurrence day in the week that hasn't passed yet."""
    skip = set(existing)
    for weekday in decode_days(task.recurrence_days or 0):
        day = week.start_date + timedelta(days=weekday)
        if day >= today and day not in skip:
            session.add(Occurrence(task=task, week=week, date=day))


def generate_recurring(session: Session, week: Week, today: date) -> None:
    """Give every open recurring task its days in this week, unless it is already planned there."""
    planned = select(Occurrence.task_id).where(Occurrence.week_id == week.id)
    tasks = session.scalars(
        select(Task).where(
            Task.kind == TaskKind.RECURRING,
            Task.status == TaskStatus.OPEN,
            Task.id.not_in(planned),
        )
    )
    for task in tasks:
        add_recurring_days(session, task, week, today)


def apply_recurrence_change(session: Session, task: Task, today: date) -> None:
    """Re-plan the remaining days (today onwards) of open weeks after the recurrence days change.

    Past days, and anything already done, skipped or missed, stay as they were.
    """
    days = set(decode_days(task.recurrence_days or 0))
    weeks = session.scalars(
        select(Week)
        .join(Occurrence, Occurrence.week_id == Week.id)
        .where(Occurrence.task_id == task.id, Week.status != WeekStatus.CLOSED)
        .distinct()
    ).all()
    for week in weeks:
        current = _occurrences_in(session, task, week)
        dropped = [
            o
            for o in current
            if o.status == OccurrenceStatus.PENDING
            and o.date is not None
            and o.date >= today
            and o.date.weekday() not in days
        ]
        delete_occurrences(session, dropped)
        kept = [o.date for o in current if o not in dropped and o.date is not None]
        add_recurring_days(session, task, week, today, existing=kept)


def remove_remaining(session: Session, task: Task, today: date) -> None:
    """Delete the task's pending occurrences that haven't happened yet. History is kept."""
    delete_occurrences(
        session,
        [o for o in _pending_in_open_weeks(session, task) if o.date is None or o.date >= today],
    )


def refresh_backlog(session: Session, task: Task) -> None:
    """An open one-off task is in the backlog when no open week holds an occurrence of it."""
    if task.kind != TaskKind.ONE_OFF:
        return
    if task.status != TaskStatus.OPEN:
        task.in_backlog = False
        return
    session.flush()
    in_open_week = session.scalar(
        select(
            exists().where(
                Occurrence.task_id == task.id,
                Occurrence.week_id == Week.id,
                Week.status != WeekStatus.CLOSED,
            )
        )
    )
    task.in_backlog = not in_open_week


def delete_occurrences(session: Session, occurrences: Sequence[Occurrence]) -> None:
    if not occurrences:
        return
    ids = [o.id for o in occurrences]
    session.execute(delete(Suggestion).where(Suggestion.occurrence_id.in_(ids)))
    for occurrence in occurrences:
        session.delete(occurrence)
    session.flush()


def _occurrences_in(session: Session, task: Task, week: Week) -> list[Occurrence]:
    return list(
        session.scalars(
            select(Occurrence).where(Occurrence.task_id == task.id, Occurrence.week_id == week.id)
        )
    )


def _pending_in_open_weeks(session: Session, task: Task) -> list[Occurrence]:
    return list(
        session.scalars(
            select(Occurrence)
            .join(Week, Occurrence.week_id == Week.id)
            .where(
                Occurrence.task_id == task.id,
                Occurrence.status == OccurrenceStatus.PENDING,
                Week.status != WeekStatus.CLOSED,
            )
        )
    )
