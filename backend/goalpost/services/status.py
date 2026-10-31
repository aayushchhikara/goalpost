"""The sidebar summary and sync history. Derived on read, never stored."""

from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from goalpost.models import Connector, Suggestion, SyncRun, Task
from goalpost.models.enums import SuggestionStatus, SyncStatus, TaskKind, TaskStatus
from goalpost.schemas.connectors import (
    ConnectorProblem,
    StatusResponse,
    SyncRunRead,
    SyncRunsResponse,
)
from goalpost.services.connectors import connector_read


def status_view(session: Session, next_sync_at: datetime | None) -> StatusResponse:
    inbox = session.scalar(
        select(func.count())
        .select_from(Suggestion)
        .where(Suggestion.status == SuggestionStatus.PENDING)
    )
    backlog = session.scalar(
        select(func.count())
        .select_from(Task)
        .where(
            Task.kind == TaskKind.ONE_OFF, Task.status == TaskStatus.OPEN, Task.in_backlog.is_(True)
        )
    )
    last_sync = session.scalar(
        select(func.max(SyncRun.finished_at)).where(
            SyncRun.status.in_([SyncStatus.OK, SyncStatus.PARTIAL])
        )
    )
    syncing = session.scalar(select(exists().where(SyncRun.finished_at.is_(None))))

    problems = []
    for row in session.scalars(select(Connector).where(Connector.enabled.is_(True))):
        view = connector_read(session, row)
        if view.pause_reason:
            problems.append(
                ConnectorProblem(
                    connector_id=row.id, name=row.name, message=view.pause_reason, paused=True
                )
            )
        elif view.last_run and view.last_run.status == SyncStatus.FAILED:
            problems.append(
                ConnectorProblem(
                    connector_id=row.id,
                    name=row.name,
                    message=view.last_run.error or "The last sync failed",
                    paused=False,
                )
            )
    return StatusResponse(
        inbox_count=inbox or 0,
        backlog_count=backlog or 0,
        syncing=bool(syncing),
        last_sync_at=last_sync,
        next_sync_at=next_sync_at,
        connector_errors=problems,
    )


def sync_runs_view(
    session: Session, connector_id: str | None, before: str | None, limit: int
) -> SyncRunsResponse:
    """Newest first. Run ids are ULIDs, so `before` pages by creation order."""
    query = select(SyncRun).order_by(SyncRun.id.desc()).limit(limit + 1)
    if connector_id:
        query = query.where(SyncRun.connector_id == connector_id)
    if before:
        query = query.where(SyncRun.id < before)
    runs = list(session.scalars(query))
    more = len(runs) > limit
    runs = runs[:limit]
    return SyncRunsResponse(
        items=[SyncRunRead.model_validate(r) for r in runs],
        next_before=runs[-1].id if more and runs else None,
    )
