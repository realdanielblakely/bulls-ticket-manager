"""
Entry point for the Bulls Ticket Manager.

Startup sequence:
  1. Create SQLite tables (idempotent)
  2. Import schedule from CSV (INSERT OR IGNORE — safe to re-run)
  3. Register APScheduler cron jobs
  4. Start the Discord bot (blocks until Ctrl-C)
"""

import asyncio
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _run_dashboard(host: str, port: int) -> None:
    """Run FastAPI/uvicorn in its own thread with its own event loop."""
    import uvicorn
    from app.dashboard.routes import dashboard_app

    async def _serve() -> None:
        config = uvicorn.Config(dashboard_app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None  # signals only work in main thread
        await server.serve()

    asyncio.run(_serve())


def main() -> None:
    from app.database import create_tables
    from app.schedule.csv_import import import_schedule
    from app.tasks.scheduler import scheduler
    from app.discord_bot.bot import client
    from app.config import settings

    log.info("Initialising database...")
    create_tables()

    log.info("Importing schedule from %s...", settings.schedule_csv_path)
    import_schedule()

    log.info(
        "Starting dashboard on http://%s:%s ...",
        settings.dashboard_host,
        settings.dashboard_port,
    )
    dashboard_thread = threading.Thread(
        target=_run_dashboard,
        args=(settings.dashboard_host, settings.dashboard_port),
        daemon=True,
    )
    dashboard_thread.start()

    log.info("Starting Discord bot (scheduler starts via setup_hook)...")
    try:
        client.run(settings.discord_bot_token, log_handler=None)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
        except Exception:
            pass


if __name__ == "__main__":
    main()
