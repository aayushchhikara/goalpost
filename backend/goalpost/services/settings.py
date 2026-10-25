from sqlalchemy import select
from sqlalchemy.orm import Session

from goalpost.models import UserSettings
from goalpost.models.base import DEFAULT_USER_ID
from goalpost.settings import get_settings


def ensure_settings(session: Session, user_id: str = DEFAULT_USER_ID) -> UserSettings:
    """Return the user's settings, seeding them from .env the first time.

    An existing row is never overwritten: once seeded, the database is the source of truth.
    """
    row = session.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if row is None:
        row = UserSettings(
            user_id=user_id,
            timezone=get_settings().timezone,
            week_start="monday",  # weeks always run Monday to Sunday
            ai_enabled=False,
        )
        session.add(row)
        session.commit()
    return row
