"""Complete, skip, reopen and move occurrences. Only explicit user actions land here.

Callers commit.
"""

from datetime import date, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from goalpost.errors import Conflict, Invalid
from goalpost.models import Occurrence
from goalpost.models.enums import OccurrenceStatus, TaskKind, TaskStatus, WeekStatus
from goalpost.services.planning import check_day, refresh_backlog, remove_remaining, week_end


def complete(session: Session, occurrence: Occurrence, now: datetime, today: date) -> Occurrence:
    if occurrence.status == OccurrenceStatus.DONE:
        raise Conflict("Occurrence is already done", code="already_done")
    if occurrence.status == OccurrenceStatus.SKIPPED:
        raise Conflict("Occurrence was skipped; reopen it first", code="skipped")
    # missed → done keeps history honest with the late flag.
    occurrence.late = occurrence.status == OccurrenceStatus.MISSED
    occurrence.status = OccurrenceStatus.DONE
    occurrence.completed_at = now

    task = occurrence.task
    if task.kind == TaskKind.ONE_OFF and task.status == TaskStatus.OPEN:
        task.status = TaskStatus.DONE
        task.in_backlog = False
        remove_remaining(session, task, today)  # a done one-off needs no other pending slot
    return occurrence


def skip(occurrence: Occurrence) -> Occurrence:
    if occurrence.status != OccurrenceStatus.PENDING:
        raise Conflict(
            f"Only pending occurrences can be skipped; this one is {occurrence.status.value}",
            code="not_pending",
        )
    occurrence.status = OccurrenceStatus.SKIPPED
    return occurrence


def reopen(session: Session, occurrence: Occurrence, today: date) -> Occurrence:
    """Undo a complete or skip. It goes back to missed if it was late or its day has passed."""
    if occurrence.status not in (OccurrenceStatus.DONE, OccurrenceStatus.SKIPPED):
        raise Conflict("Only done or skipped occurrences can be reopened", code="not_reopenable")
    passed = (occurrence.date or week_end(occurrence.week_start)) < today
    occurrence.status = (
        OccurrenceStatus.MISSED if occurrence.late or passed else OccurrenceStatus.PENDING
    )
    occurrence.late = False
    occurrence.completed_at = None

    task = occurrence.task
    if task.kind == TaskKind.ONE_OFF and task.status == TaskStatus.DONE:
        task.status = TaskStatus.OPEN
        refresh_backlog(session, task)
    return occurrence


def move(session: Session, occurrence: Occurrence, day: date | None, today: date) -> Occurrence:
    """Move to another remaining day of the same week, or to "any day" (one-off only)."""
    task = occurrence.task
    if occurrence.week.status == WeekStatus.CLOSED:
        raise Conflict("The occurrence's week is closed", code="week_closed")
    movable = occurrence.status == OccurrenceStatus.PENDING or (
        occurrence.status == OccurrenceStatus.MISSED and task.kind == TaskKind.ONE_OFF
    )
    if not movable:
        raise Conflict(
            f"A {occurrence.status.value} occurrence can't be moved"
            " (missed recurring days stay missed)",
            code="not_movable",
        )
    if day is None:
        if task.kind == TaskKind.RECURRING:
            raise Invalid("Recurring occurrences need a day", field="date")
    else:
        check_day(occurrence.week, day, today)
        taken = exists().where(
            Occurrence.task_id == task.id,
            Occurrence.week_id == occurrence.week_id,
            Occurrence.date == day,
            Occurrence.id != occurrence.id,
        )
        if session.scalar(select(taken)):
            raise Conflict(f"Task already has an occurrence on {day}", code="already_planned")
    occurrence.date = day
    occurrence.status = OccurrenceStatus.PENDING
    return occurrence
