from fastapi import APIRouter

from goalpost import __version__
from goalpost.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
