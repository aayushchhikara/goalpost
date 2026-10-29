from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, status
from sqlalchemy import select

from goalpost.api.deps import RegistryDep, SessionDep, SessionFactoryDep
from goalpost.models import Connector
from goalpost.models.enums import SyncTrigger
from goalpost.scheduler import next_sync_at
from goalpost.schemas.connectors import StatusResponse, SyncRequest, SyncRunsResponse, SyncStarted
from goalpost.services.connectors import get_connector
from goalpost.services.status import status_view, sync_runs_view
from goalpost.services.sync import sync_connectors

router = APIRouter(tags=["sync"])


@router.post(
    "/sync",
    response_model=SyncStarted,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startSync",
)
def start_sync(
    body: SyncRequest,
    session: SessionDep,
    factory: SessionFactoryDep,
    registry: RegistryDep,
    background: BackgroundTasks,
) -> SyncStarted:
    """Sync now: one connector, or every enabled one. Returns at once; poll /status."""
    if body.connector_id:
        ids = [get_connector(session, body.connector_id).id]
    else:
        ids = list(session.scalars(select(Connector.id).where(Connector.enabled.is_(True))))
    background.add_task(sync_connectors, factory, registry, SyncTrigger.MANUAL, ids)
    return SyncStarted(connector_ids=ids)


@router.get("/sync/runs", response_model=SyncRunsResponse, operation_id="getSyncRuns")
def get_sync_runs(
    session: SessionDep,
    connector_id: str | None = None,
    before: Annotated[str | None, Query(description="next_before from the previous page")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SyncRunsResponse:
    """Sync history, newest first."""
    return sync_runs_view(session, connector_id, before, limit)


@router.get("/status", response_model=StatusResponse, operation_id="getStatus")
def get_status(session: SessionDep) -> StatusResponse:
    """Sidebar summary: inbox and backlog counts, last and next sync, connector errors."""
    return status_view(session, next_sync_at())
