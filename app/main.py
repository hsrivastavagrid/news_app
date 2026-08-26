import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import BASE_DIR, FETCH_ON_START, SCHEDULER_ENABLED
from app.database import db
from app.logging_config import setup_logging
from app.middleware import RequestLoggingMiddleware
from app.services.news_fetcher import fetch_and_process_news
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.filter_agent import parse_priority_message, to_preferences
from app.models import (
    TagInfoSchema,
    DashboardModeSchema,
    TrendPointSchema,
    ArticleSchema,
    ContagionEventSchema,
    PreferenceSchema,
    AgentFilterRequest,
    AgentFilterResponse,
)

logger = logging.getLogger("newspulse.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("startup begin")
    try:
        db.init_db()
        logger.info("database ready")
        if FETCH_ON_START:
            logger.info("startup fetch begin")
            count = fetch_and_process_news()
            logger.info("startup fetch done articles=%s", count)
        if SCHEDULER_ENABLED:
            start_scheduler()
        logger.info("startup complete")
    except Exception:
        logger.exception("startup failed")
        raise
    yield
    logger.info("shutdown begin")
    if SCHEDULER_ENABLED:
        stop_scheduler()
    logger.info("shutdown complete")


app = FastAPI(
    title="NewsPulse — Personalized News Sentiment API",
    description="Self-contained backend: hourly ingest, VADER sentiment, tags, agent filters.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    if isinstance(exc, (HTTPException, StarletteHTTPException, RequestValidationError)):
        raise exc
    logger.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc),
            "request_id": getattr(request.state, "request_id", "-"),
        },
    )


def parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [t.strip().lower() for t in value.split(",") if t.strip()]


def rolling_window():
    return db.get_rolling_window()


@app.get("/api/tags", response_model=List[TagInfoSchema])
def get_tags():
    win_from, win_to = rolling_window()
    logger.info("activity tags window=%s..%s", win_from, win_to)
    return db.get_all_tags_with_metadata(time_from=win_from, time_to=win_to)


@app.get("/api/dashboard", response_model=DashboardModeSchema)
def get_dashboard(
    tags: Optional[str] = Query(None),
    sentiments: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    tag_mode: str = Query("union"),
):
    tag_list = parse_csv(tags)
    sent_list = parse_csv(sentiments)
    kw_list = [k for k in (keywords or "").split(",") if k.strip()]
    win_from, win_to = rolling_window()
    logger.info(
        "activity dashboard tags=%s sentiments=%s keywords=%s tag_mode=%s",
        tag_list,
        sent_list,
        kw_list,
        tag_mode,
    )
    mode = db.get_dashboard_mode(
        tags=tag_list,
        time_from=win_from,
        time_to=win_to,
        tag_mode=tag_mode,
        sentiments=sent_list or None,
        keywords=kw_list or None,
    )
    return mode.model_copy(update={"window_from": win_from, "window_to": win_to})


@app.get("/api/trends", response_model=List[TrendPointSchema])
def get_trends(
    tags: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    logger.info("activity trends tags=%s hours=%s", parse_csv(tags), hours)
    return db.get_trends(parse_csv(tags), hours=hours)


@app.get("/api/articles", response_model=List[ArticleSchema])
def get_articles(
    tags: Optional[str] = Query(None, description="Comma-separated domain tags"),
    sentiment: Optional[str] = Query(None, description="Single sentiment (legacy)"),
    sentiments: Optional[str] = Query(None, description="Comma-separated: good,bad,ugly,neutral"),
    keywords: Optional[str] = Query(None, description="Comma-separated keyword matches"),
    tag_mode: str = Query("union", description="union (any tag) or intersection (all tags)"),
    limit: int = Query(100, ge=1, le=200),
):
    tag_list = parse_csv(tags)
    sent_list = parse_csv(sentiments)
    kw_list = [k.strip() for k in (keywords or "").split(",") if k.strip()]
    win_from, win_to = rolling_window()
    logger.info(
        "activity articles tags=%s sentiments=%s keywords=%s tag_mode=%s limit=%s",
        tag_list,
        sent_list or sentiment,
        kw_list,
        tag_mode,
        limit,
    )
    return db.get_articles(
        tags=tag_list,
        sentiment=sentiment,
        sentiments=sent_list or None,
        keywords=kw_list or None,
        tag_mode=tag_mode,
        time_from=win_from,
        time_to=win_to,
        limit=limit,
    )


@app.get("/api/contagion", response_model=List[ContagionEventSchema])
def get_contagion_alerts():
    alerts = db.get_active_contagion_alerts()
    logger.info("activity contagion count=%s", len(alerts))
    return alerts


@app.get("/api/preferences", response_model=PreferenceSchema)
def get_preferences():
    prefs = db.get_preferences()
    logger.info("activity preferences_get tags=%s sentiments=%s", prefs.tags, prefs.sentiments)
    return prefs


@app.put("/api/preferences", response_model=PreferenceSchema)
def put_preferences(body: PreferenceSchema):
    logger.info(
        "activity preferences_save tags=%s sentiments=%s keywords=%s tag_mode=%s",
        body.tags,
        body.sentiments,
        body.keywords,
        body.tag_mode,
    )
    return db.save_preferences(body)


@app.post("/api/agent/filter", response_model=AgentFilterResponse)
def agent_filter(body: AgentFilterRequest):
    logger.info("activity agent_filter persist=%s message_len=%s", body.persist, len(body.message or ""))
    try:
        result = parse_priority_message(body.message)
    except Exception:
        logger.exception("agent filter failed")
        raise
    logger.info(
        "activity agent_filter result tags=%s sentiments=%s keywords=%s",
        result.tags,
        result.sentiments,
        result.keywords,
    )
    if body.persist:
        db.save_preferences(to_preferences(result))
        result.persisted = True
        logger.info("activity agent_filter persisted=true")
    return result


@app.post("/api/fetch-now")
def trigger_fetch_now():
    logger.info("activity fetch-now begin")
    try:
        new_count = fetch_and_process_news()
    except Exception:
        logger.exception("fetch-now failed")
        raise
    logger.info("activity fetch-now done articles=%s", new_count)
    return {
        "status": "success",
        "message": f"Fetch cycle executed. Processed {new_count} articles.",
        "new_articles_count": new_count,
    }


frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
