from apscheduler.schedulers.background import BackgroundScheduler
from app.config import FETCH_INTERVAL_MINUTES
from app.services.news_fetcher import fetch_and_process_news

scheduler = BackgroundScheduler()

def start_scheduler():
    """Starts background hourly news ingestion scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            fetch_and_process_news,
            "interval",
            minutes=FETCH_INTERVAL_MINUTES,
            id="news_fetch_job",
            replace_existing=True,
        )
        scheduler.start()
        print(f"[Scheduler] Ingestion background job started (Interval: {FETCH_INTERVAL_MINUTES} mins).")

def stop_scheduler():
    """Stops background scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Ingestion background job stopped.")
