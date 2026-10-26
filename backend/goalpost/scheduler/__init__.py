"""Background jobs. The close job runs at local midnight; sync jobs join in M3."""

from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from goalpost.db import get_engine
from goalpost.services.close import close_due
from goalpost.services.dates import local_date
from goalpost.services.settings import ensure_settings


def run_close_job() -> None:
    with Session(get_engine()) as session:
        timezone = ensure_settings(session).timezone
        close_due(session, local_date(datetime.now(UTC), timezone))
        session.commit()


def start_scheduler(timezone: str) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(
        run_close_job,
        CronTrigger(hour=0, minute=0, second=5, timezone=timezone),
        id="close",
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
