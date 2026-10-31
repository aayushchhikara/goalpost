from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from goalpost.db import get_session_factory
from goalpost.sdk.loader import Registry
from goalpost.services.connectors import installed_connectors
from goalpost.services.dates import local_date
from goalpost.services.settings import ensure_settings

SessionFactoryDep = Annotated[sessionmaker[Session], Depends(get_session_factory)]


def get_session(factory: SessionFactoryDep) -> Iterator[Session]:
    with factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
RegistryDep = Annotated[Registry, Depends(installed_connectors)]


def get_now() -> datetime:
    """The current time in UTC. Tests override this to freeze the clock."""
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(get_now)]


def get_today(session: SessionDep, now: NowDep) -> date:
    """Today in the user's timezone."""
    return local_date(now, ensure_settings(session).timezone)


TodayDep = Annotated[date, Depends(get_today)]
