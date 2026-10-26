"""The close job: mark passed days missed, close finished weeks, return one-offs to the backlog.

Runs at midnight, on startup, and on demand. Safe to run any number of times.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from goalpost.models import Occurrence, Task, Week
from goalpost.models.enums import OccurrenceStatus, TaskKind, TaskStatus, WeekStatus
from goalpost.schemas.planning import CloseResult
from goalpost.services.planning import refresh_backlog, week_end


def close_due(session: Session, today: date) -> CloseResult:
    """Bring statuses up to date as of `today` (the user's local date). Callers commit."""
    activated = []
    for week in session.scalars(
        select(Week).where(Week.status == WeekStatus.PLANNING, Week.start_date <= today)
    ).all():
        if week_end(week.start_date) >= today:
            week.status = WeekStatus.ACTIVE
            activated.append(week.start_date)

    # Dated occurrences become missed once their day ends.
    missed = 0
    for occurrence in session.scalars(
        select(Occurrence).where(
            Occurrence.status == OccurrenceStatus.PENDING,
            Occurrence.date.is_not(None),
            Occurrence.date < today,
        )
    ).all():
        occurrence.status = OccurrenceStatus.MISSED
        missed += 1

    # Weeks close once their Sunday ends; their "any day" occurrences become missed too.
    closing = session.scalars(
        select(Week).where(
            Week.status != WeekStatus.CLOSED, Week.start_date < today - timedelta(days=6)
        )
    ).all()
    closing_ids = [w.id for w in closing]
    for occurrence in session.scalars(
        select(Occurrence).where(
            Occurrence.week_id.in_(closing_ids),
            Occurrence.status == OccurrenceStatus.PENDING,
        )
    ).all():
        occurrence.status = OccurrenceStatus.MISSED
        missed += 1
    for week in closing:
        week.status = WeekStatus.CLOSED
    session.flush()

    # Unfinished one-offs from closed weeks go back to the backlog. Recurring days just stay missed.
    returned = 0
    for task in session.scalars(
        select(Task)
        .join(Occurrence, Occurrence.task_id == Task.id)
        .where(
            Occurrence.week_id.in_(closing_ids),
            Task.kind == TaskKind.ONE_OFF,
            Task.status == TaskStatus.OPEN,
        )
        .distinct()
    ).all():
        was_in_backlog = task.in_backlog
        refresh_backlog(session, task)
        if task.in_backlog and not was_in_backlog:
            returned += 1

    return CloseResult(
        activated_weeks=activated,
        closed_weeks=[w.start_date for w in closing],
        missed=missed,
        returned_to_backlog=returned,
    )
