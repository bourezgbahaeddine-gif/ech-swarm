"""MSI scheduled jobs (daily/weekly watchlist runs)."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.logging import get_logger
from app.msi.service import msi_monitor_service

settings = get_settings()
logger = get_logger("msi.scheduler")

_scheduler: AsyncIOScheduler | None = None


def start_msi_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler(timezone=settings.msi_timezone)
    _scheduler.add_job(
        msi_monitor_service.run_watchlist_mode,
        trigger=CronTrigger(hour=settings.msi_daily_hour, minute=settings.msi_daily_minute, timezone=settings.msi_timezone),
        args=["daily"],
        id="msi_daily_watchlist",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        msi_monitor_service.run_watchlist_mode,
        trigger=CronTrigger(
            day_of_week=settings.msi_weekly_day_of_week,
            hour=settings.msi_weekly_hour,
            minute=settings.msi_weekly_minute,
            timezone=settings.msi_timezone,
        ),
        args=["weekly"],
        id="msi_weekly_watchlist",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "msi_scheduler_started",
        timezone=settings.msi_timezone,
        daily=f"{settings.msi_daily_hour:02d}:{settings.msi_daily_minute:02d}",
        weekly=f"{settings.msi_weekly_day_of_week} {settings.msi_weekly_hour:02d}:{settings.msi_weekly_minute:02d}",
    )


def stop_msi_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("msi_scheduler_stopped")
