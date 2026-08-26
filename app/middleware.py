import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import new_request_id

logger = logging.getLogger("newspulse.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or new_request_id()
        request.state.request_id = rid
        start = time.perf_counter()
        path = request.url.path
        query = request.url.query
        logger.info(
            "request start method=%s path=%s query=%s client=%s",
            request.method,
            path,
            query or "-",
            request.client.host if request.client else "-",
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request failed method=%s path=%s duration_ms=%.1f",
                request.method,
                path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        log_fn = logger.error if status >= 500 else logger.warning if status >= 400 else logger.info
        log_fn(
            "request end method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            path,
            status,
            elapsed_ms,
        )
        response.headers["X-Request-ID"] = rid
        return response
