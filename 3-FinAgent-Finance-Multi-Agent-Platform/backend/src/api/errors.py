"""Exception handlers: every error becomes ``{"error": {code, message, requestId}}``.

Unexpected exceptions are logged with their stack trace server-side and reported to the client as
a generic 500 — never with internals.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.context import current_request_id
from src.core.errors import AppError, RateLimited

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


def _body(code: str, message: str, details: object | None = None) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message, "requestId": current_request_id()}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):  # registered for this type only
        raise TypeError(type(exc).__name__)
    log = logger.warning if exc.status_code < 500 else logger.error
    log("request failed", extra={"code": exc.code, "status": exc.status_code, **exc.details})
    headers = {}
    if isinstance(exc, RateLimited) and exc.retry_after is not None:
        headers["Retry-After"] = str(max(1, round(exc.retry_after)))
    return JSONResponse(
        exc.to_dict(current_request_id()), status_code=exc.status_code, headers=headers
    )


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # registered for this type only
        raise TypeError(type(exc).__name__)
    details = [
        {
            "loc": [str(p) for p in e.get("loc", ())],
            "msg": e.get("msg", ""),
            "type": e.get("type", ""),
        }
        for e in exc.errors()
    ]
    return JSONResponse(
        _body("validation_failed", "Request validation failed", details), status_code=422
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # registered for this type only
        raise TypeError(type(exc).__name__)
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
    return JSONResponse(
        _body(code, message), status_code=exc.status_code, headers=getattr(exc, "headers", None)
    )


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    return JSONResponse(_body("internal_error", "Internal server error"), status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled)
