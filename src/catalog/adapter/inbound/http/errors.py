"""The single error envelope (07-api/guidelines.md, _shared.yaml) and the one place where
an error becomes a status code (Annex C): the domain raises typed errors and knows
nothing about HTTP."""
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# The X-Correlation-Id of the request being served: the traceId of the envelope and a
# field of every log line.
CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="")


class ApiError(Exception):
    def __init__(self, status: int, error: str, message: str, details: list[dict] | None = None):
        super().__init__(message)
        self.status, self.error, self.message, self.details = status, error, message, details


def validation_error(details: list[dict]) -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", "the request has invalid fields", details)


def respond(status: int, error: str, message: str, details: list[dict] | None = None) -> JSONResponse:
    body: dict = {"error": error, "message": message}
    if details:
        body["details"] = details
    body["traceId"] = CORRELATION_ID.get()
    return JSONResponse(status_code=status, content=body)


def _field_message(error: dict) -> dict:
    field = str(error["loc"][-1]) if error.get("loc") else "request"
    return {"field": field, "message": str(error.get("msg", "is invalid")).removeprefix("Value error, ")}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError) -> JSONResponse:
        return respond(e.status, e.error, e.message, e.details)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        return respond(400, "VALIDATION_ERROR", "the request has invalid fields",
                       [_field_message(error) for error in e.errors()])

    @app.exception_handler(StarletteHTTPException)
    async def routing(_: Request, e: StarletteHTTPException) -> JSONResponse:
        if e.status_code == 405:
            return respond(405, "NOT_FOUND", "method not allowed on this route")
        if e.status_code == 404:
            return respond(404, "NOT_FOUND", "the route does not exist")
        return respond(e.status_code, "INTERNAL_ERROR", "internal server error")
