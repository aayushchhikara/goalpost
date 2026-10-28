from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config(url: str | None = None) -> Config:
    from goalpost.settings import get_settings

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", (url or get_settings().database_url).replace("%", "%%"))
    return cfg


def run_migrations(url: str | None = None) -> None:
    """Upgrade the database to head. Defaults to the configured database."""
    from goalpost.db import get_engine, make_engine

    # Creating the engine first creates the data directory before Alembic opens the SQLite file.
    if url is None:
        get_engine()
    else:
        make_engine(url).dispose()
    command.upgrade(alembic_config(url), "head")
