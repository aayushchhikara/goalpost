import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("GOALPOST_TIMEZONE", "UTC")
os.environ.setdefault("GOALPOST_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("GOALPOST_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

from goalpost.db import make_engine  # noqa: E402
from goalpost.migrate import run_migrations  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


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
