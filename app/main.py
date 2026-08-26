from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import db
from app.services.news_fetcher import fetch_and_process_news
from app.services.scheduler import start_scheduler, stop_scheduler
from app.models import (
    TagInfoSchema,
    DashboardModeSchema,
    TrendPointSchema,
    ArticleSchema,
    ContagionEventSchema,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    db.init_db()
    # Initial data fetch on startup
    fetch_and_process_news()
    # Start background scheduler
    start_scheduler()
    yield
    # Shutdown logic
    stop_scheduler()

app = FastAPI(
    title="NewsPulse — Real-Time News Sentiment Analysis API",
    description="Multi-tag news sentiment intelligence platform with cross-domain contagion alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_tags_param(tags: Optional[str]) -> List[str]:
    """Helper to parse comma-separated tags string into a list."""
    if not tags:
        return []
    return [t.strip().lower() for t in tags.split(",") if t.strip()]

@app.get("/api/tags", response_model=List[TagInfoSchema])
def get_tags():
    """Returns all domain tags with article count and dominant sentiment mode."""
    return db.get_all_tags_with_metadata()

@app.get("/api/dashboard", response_model=DashboardModeSchema)
def get_dashboard(tags: Optional[str] = Query(None, description="Comma-separated domain tags")):
    """
    Returns sentiment mode breakdown dynamically calculated for tag intersection.
    If no tags specified, returns overall news mood across all articles.
    """
    tag_list = parse_tags_param(tags)
    return db.get_dashboard_mode(tag_list)

@app.get("/api/trends", response_model=List[TrendPointSchema])
def get_trends(
    tags: Optional[str] = Query(None, description="Comma-separated domain tags"),
    hours: int = Query(24, ge=1, le=168),
):
    """Returns hourly time-series trend data for tag intersection."""
    tag_list = parse_tags_param(tags)
    return db.get_trends(tag_list, hours=hours)

@app.get("/api/articles", response_model=List[ArticleSchema])
def get_articles(
    tags: Optional[str] = Query(None, description="Comma-separated domain tags"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment: good, bad, ugly, neutral"),
    limit: int = Query(50, ge=1, le=100),
):
    """Fetches articles matching tag intersection and optional sentiment mode."""
    tag_list = parse_tags_param(tags)
    return db.get_articles(tags=tag_list, sentiment=sentiment, limit=limit)

@app.get("/api/contagion", response_model=List[ContagionEventSchema])
def get_contagion_alerts():
    """Returns active cross-domain sentiment contagion alerts."""
    return db.get_active_contagion_alerts()

@app.post("/api/fetch-now")
def trigger_fetch_now():
    """Manually triggers an immediate news fetch & analysis cycle."""
    new_count = fetch_and_process_news()
    return {
        "status": "success",
        "message": f"Fetch cycle executed successfully. Processed {new_count} new articles.",
        "new_articles_count": new_count,
    }

# Mount static files for SPA frontend
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
