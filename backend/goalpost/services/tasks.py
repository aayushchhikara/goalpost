"""Task create, edit and drop. Callers commit."""

from datetime import date

from sqlalchemy.orm import Session

from goalpost.errors import Conflict, Invalid
from goalpost.models import Task
from goalpost.models.enums import TaskKind, TaskStatus
from goalpost.schemas.planning import TaskCreate, TaskUpdate
from goalpost.services.dates import encode_days
from goalpost.services.planning import apply_recurrence_change, plan_week, remove_remaining


def create_task(session: Session, data: TaskCreate, today: date) -> Task:
    recurring = data.kind == TaskKind.RECURRING
    task = Task(
        title=data.title,
        notes=data.notes,
        kind=data.kind,
        priority=data.priority,
        recurrence_days=encode_days(data.recurrence_days or []) if recurring else None,
        in_backlog=not recurring,  # recurring tasks never sit in the backlog
    )
    session.add(task)
    session.flush()
    if data.plan is not None:
        plan_week(session, data.plan.week_start, [(task.id, data.plan.date)], today)
    return task


def update_task(session: Session, task: Task, data: TaskUpdate, today: date) -> Task:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    days = changes.pop("recurrence_days", None)
    for field, value in changes.items():
        setattr(task, field, value)
    if days is not None:
        if task.kind != TaskKind.RECURRING:
            raise Invalid("Only recurring tasks have recurrence days", field="recurrence_days")
        mask = encode_days(days)
        if mask != task.recurrence_days:
            task.recurrence_days = mask
            apply_recurrence_change(session, task, today)
    return task


def drop_task(session: Session, task: Task, today: date) -> Task:
    if task.status != TaskStatus.OPEN:
        raise Conflict(f"Task is already {task.status.value}", code="task_not_open")
    task.status = TaskStatus.DROPPED
    task.in_backlog = False
    remove_remaining(session, task, today)
    return task
