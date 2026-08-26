import logging
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import LOG_FILE, LOG_LEVEL

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    request_id_ctx.set(rid)
    return rid


def setup_logging() -> logging.Logger:
    """Configure stdout + rotating file logs. Safe to call more than once."""
    level = getattr(logging, str(LOG_LEVEL).upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | rid=%(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    rid_filter = RequestIdFilter()

    root = logging.getLogger()
    root.setLevel(level)

    if not any(getattr(h, "_newspulse", False) for h in root.handlers):
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        stream.addFilter(rid_filter)
        stream._newspulse = True  # type: ignore[attr-defined]
        root.addHandler(stream)

        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(rid_filter)
        file_handler._newspulse = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    logger = logging.getLogger("newspulse")
    logger.debug("Logging initialized level=%s file=%s", LOG_LEVEL, LOG_FILE)
    return logger
