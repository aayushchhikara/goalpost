import pytest
from goalpost.models import UserSettings
from goalpost.services.settings import ensure_settings
from goalpost.settings import Settings
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_ensure_settings_seeds_from_env(db_session: Session) -> None:
    row = ensure_settings(db_session)
    assert row.timezone == "UTC"  # GOALPOST_TIMEZONE in conftest
    assert row.week_start == "monday"
    assert row.ai_enabled is False


def test_ensure_settings_is_idempotent_and_keeps_edits(db_session: Session) -> None:
    row = ensure_settings(db_session)
    row.timezone = "Asia/Kolkata"
    db_session.commit()

    again = ensure_settings(db_session)
    assert again.id == row.id
    assert again.timezone == "Asia/Kolkata"
    assert db_session.scalar(select(func.count()).select_from(UserSettings)) == 1


def test_unknown_timezone_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOALPOST_TIMEZONE", "Mars/Olympus")
    with pytest.raises(ValueError, match="unknown IANA timezone"):
        Settings()  # type: ignore[call-arg]
