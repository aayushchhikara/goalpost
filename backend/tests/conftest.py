import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("GOALPOST_TIMEZONE", "UTC")
os.environ.setdefault("GOALPOST_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("GOALPOST_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

from fastapi.testclient import TestClient  # noqa: E402
from goalpost.api.deps import get_now  # noqa: E402
from goalpost.db import get_session, make_engine  # noqa: E402
from goalpost.main import app  # noqa: E402
from goalpost.migrate import run_migrations  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

# The API only answers to localhost, so tests address it the way a browser on this machine does.
BASE_URL = "http://localhost"


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """A fresh SQLite database migrated to head."""
    url = f"sqlite:///{tmp_path / 'goalpost.db'}"
    run_migrations(url)
    return url


@pytest.fixture
def db_session(db_url: str) -> Iterator[Session]:
    engine = make_engine(db_url)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


class Clock:
    now = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)  # Monday of week 44 (settings timezone is UTC)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(db_url: str, clock: Clock) -> Iterator[TestClient]:
    """The API on a fresh database with a frozen clock. No lifespan, so no scheduler."""
    engine = make_engine(db_url)
    make_session = sessionmaker(engine, expire_on_commit=False)

    def session() -> Iterator[Any]:
        with make_session() as s:
            yield s

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_now] = lambda: clock.now
    yield TestClient(app, base_url=BASE_URL)
    app.dependency_overrides.clear()
    engine.dispose()
