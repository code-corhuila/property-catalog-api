"""The FastAPI application: correlation, one JSON log line per request, the error
envelope and /health (Annex C; numeral 5.3.9)."""
import json
import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import FastAPI, Request

from catalog.adapter.inbound.http import errors

HEADER = "X-Correlation-Id"
log = logging.getLogger("catalog.http")


def _utc(seconds: float | None = None) -> str:
    moment = datetime.now(timezone.utc) if seconds is None else datetime.fromtimestamp(seconds, timezone.utc)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the field names of the Java services (ECS)."""

    def format(self, record: logging.LogRecord) -> str:
        line = {"@timestamp": _utc(record.created), "log.level": record.levelname,
                "log.logger": record.name, "service.name": "catalog-api", "message": record.getMessage()}
        correlation_id = errors.CORRELATION_ID.get()
        if correlation_id:
            line["correlationId"] = correlation_id
        if record.exc_info:
            line["error.stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True   # the middleware writes the access line


def create_app(database_ok: Callable[[], bool]) -> FastAPI:
    app = FastAPI(title="catalog-api", docs_url=None, redoc_url=None, openapi_url=None)
    errors.install(app)

    @app.get("/health")
    def health() -> dict:
        """Answers without a token, outside /api/v1; a dependency that is down is
        reported inside the 200 (catalog-service.yaml, getHealth)."""
        try:
            database = "ok" if database_ok() else "down"
        except Exception:
            database = "down"
        return {"status": "ok" if database == "ok" else "degraded", "timestamp": _utc(),
                "dependencies": {"database": database}}

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        correlation_id = request.headers.get(HEADER, "")
        if not correlation_id.strip() or len(correlation_id) > 128:
            correlation_id = str(uuid.uuid4())
        token = errors.CORRELATION_ID.set(correlation_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The detail goes only to the log; the client gets a neutral message.
            log.exception("unhandled error")
            response = errors.respond(500, "INTERNAL_ERROR", "internal server error")
        response.headers[HEADER] = correlation_id
        log.info("request method=%s path=%s status=%s durationMs=%d", request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
        errors.CORRELATION_ID.reset(token)
        return response

    return app
