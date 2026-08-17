"""Logging, request correlation, and the one thing that makes 500s diagnosable."""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"

_QUIET_PATHS = {"/health", "/health/ready", "/favicon.ico"}

_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_NOISY_LOGGERS = {"httpx": logging.WARNING, "httpcore": logging.WARNING,
                  "python_multipart": logging.WARNING}

log = logging.getLogger("app.request")


class _RequestIdFilter(logging.Filter):
    """Puts the current request id on every record, including third-party ones."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for a log collector rather than a person."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, _DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Install one handler on the root logger."""
    root = logging.getLogger()
    level = getattr(logging, settings.LOG_LEVEL.strip().upper(), logging.INFO)
    root.setLevel(level)

    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if settings.LOG_JSON
        else logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    for name, floor in _NOISY_LOGGERS.items():
        logging.getLogger(name).setLevel(floor)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """One log line per request, with a correlation id and a duration."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        path = request.url.path

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log.exception(
                "%s %s failed after %.0fms", request.method, path, elapsed_ms,
                extra={"extra_fields": {"method": request.method, "path": path,
                                        "duration_ms": round(elapsed_ms, 1)}},
            )
            request_id_var.reset(token)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error.", "request_id": request_id},
                headers={REQUEST_ID_HEADER: request_id},
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        if path in _QUIET_PATHS:
            level = logging.DEBUG
        elif response.status_code >= 500:
            level = logging.ERROR
        else:
            level = logging.INFO
        log.log(
            level, "%s %s -> %s in %.0fms",
            request.method, path, response.status_code, elapsed_ms,
            extra={"extra_fields": {"method": request.method, "path": path,
                                    "status": response.status_code,
                                    "duration_ms": round(elapsed_ms, 1)}},
        )
        request_id_var.reset(token)
        return response
