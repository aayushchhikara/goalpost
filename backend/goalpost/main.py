from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from goalpost.api import health
from goalpost.db import get_engine
from goalpost.migrate import run_migrations
from goalpost.services.settings import ensure_settings
from goalpost.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    run_migrations()
    with Session(get_engine()) as session:
        ensure_settings(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast, naming any missing required key
    app = FastAPI(title="Goalpost", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
