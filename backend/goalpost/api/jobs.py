from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from goalpost.api.deps import SessionDep, TodayDep
from goalpost.schemas.planning import CloseResult
from goalpost.services.close import close_due

router = APIRouter(prefix="/jobs", tags=["jobs"])

AsOf = Annotated[
    date | None,
    Query(description="Run as if it were this day. Testing only: a future day closes weeks early."),
]


@router.post("/close", response_model=CloseResult, operation_id="runCloseJob")
def run_close_job(
    session: SessionDep,
    today: TodayDep,
    as_of: AsOf = None,
) -> CloseResult:
    """Run the close job now. It also runs at midnight and on startup."""
    result = close_due(session, as_of or today)
    session.commit()
    return result
