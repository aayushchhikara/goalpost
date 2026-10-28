from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from goalpost.api import health, v1
from goalpost.db import get_engine
from goalpost.errors import install_error_handlers
from goalpost.migrate import run_migrations
from goalpost.scheduler import run_close_job, start_scheduler
from goalpost.security import LocalOnlyMiddleware
from goalpost.services.settings import ensure_settings
from goalpost.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    run_migrations()
    with Session(get_engine()) as session:
        timezone = ensure_settings(session).timezone
    run_close_job()  # catch up on days that ended while the app was off
    scheduler = start_scheduler(timezone)
    yield
    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast, naming any missing required key
    app = FastAPI(title="Goalpost", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    # Added last so it runs first: refuse foreign hosts and cross-site writes before anything else.
    app.add_middleware(
        LocalOnlyMiddleware,
        allowed_hosts=settings.allowed_hosts,
        allowed_origins=[settings.frontend_origin],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(v1.router)
    return app


app = create_app()
