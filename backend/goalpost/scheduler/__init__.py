"""Background jobs: the close job at local midnight, and syncs on startup and every 4 hours."""

from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from goalpost.db import get_engine, get_session_factory
from goalpost.models.enums import SyncTrigger
from goalpost.services.close import close_due
from goalpost.services.connectors import installed_connectors
from goalpost.services.dates import local_date
from goalpost.services.settings import ensure_settings
from goalpost.services.sync import sync_connectors

SYNC_EVERY_HOURS = 4

_scheduler: BackgroundScheduler | None = None


def run_close_job() -> None:
    with Session(get_engine()) as session:
        timezone = ensure_settings(session).timezone
        close_due(session, local_date(datetime.now(UTC), timezone))
        session.commit()


def run_sync(trigger: SyncTrigger) -> None:
    sync_connectors(get_session_factory(), installed_connectors(), trigger)


def start_scheduler(timezone: str) -> BackgroundScheduler:
    global _scheduler
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(
        run_close_job,
        CronTrigger(hour=0, minute=0, second=5, timezone=timezone),
        id="close",
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_sync,
        IntervalTrigger(hours=SYNC_EVERY_HOURS),
        args=[SyncTrigger.SCHEDULE],
        id="sync",
        coalesce=True,
        max_instances=1,
    )
    # Catch up after the machine was off or asleep, without holding up startup.
    scheduler.add_job(run_sync, args=[SyncTrigger.STARTUP], id="startup-sync")
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def next_sync_at() -> datetime | None:
    job = _scheduler.get_job("sync") if _scheduler else None
    return job.next_run_time if job else None
