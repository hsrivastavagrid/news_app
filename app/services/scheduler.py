import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import FETCH_INTERVAL_MINUTES
from app.services.news_fetcher import fetch_and_process_news

logger = logging.getLogger("newspulse.scheduler")
scheduler = BackgroundScheduler()


def _run_fetch_job():
    logger.info("scheduled fetch begin interval_minutes=%s", FETCH_INTERVAL_MINUTES)
    try:
        count = fetch_and_process_news()
        logger.info("scheduled fetch done articles=%s", count)
    except Exception:
        logger.exception("scheduled fetch failed")


def start_scheduler():
    """Starts background hourly news ingestion scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            _run_fetch_job,
            "interval",
            minutes=FETCH_INTERVAL_MINUTES,
            id="news_fetch_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("scheduler started interval_minutes=%s", FETCH_INTERVAL_MINUTES)

def stop_scheduler():
    """Stops background scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("scheduler stopped")
