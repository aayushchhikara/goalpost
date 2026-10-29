from typing import Any

from fastapi import APIRouter

from goalpost.api import connectors, jobs, occurrences, sync, tasks, weeks
from goalpost.schemas.errors import ErrorResponse

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (404, 409, 422)
}

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
router.include_router(tasks.router)
router.include_router(weeks.router)
router.include_router(occurrences.router)
router.include_router(jobs.router)
router.include_router(connectors.router)
router.include_router(sync.router)
