"""
APScheduler cron job definitions.

The scheduler shares the Discord bot's asyncio event loop so async coroutines
(like send_weekly_prompt) can be scheduled directly.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/New_York")


def setup_jobs() -> None:
    """Register all cron jobs. Call this before starting the scheduler."""

    # Weekly prompt: every Sunday at 10:00 AM Eastern
    scheduler.add_job(
        _run_weekly_prompt,
        trigger="cron",
        day_of_week="sun",
        hour=10,
        minute=0,
        id="weekly_prompt",
        replace_existing=True,
    )
    log.info("Scheduled weekly_prompt job (Sun 10:00 AM ET)")


async def _run_weekly_prompt() -> None:
    from app.discord_bot.weekly_prompt import send_weekly_prompt
    try:
        await send_weekly_prompt()
    except Exception:
        log.exception("weekly_prompt job failed")
