"""Request ID, audit logging, metrics, security headers and error mapping."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.context import new_request_id, request_id_var, user_id_var
from app.core.errors import AppError, RateLimited
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS

logger = logging.getLogger(__name__)
audit = logging.getLogger("audit")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if incoming.startswith("REQ-") and len(incoming) <= 40 else new_request_id()
        request_id_var.set(rid)
        user_id_var.set("-")
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            HTTP_LATENCY.labels(request.method, path, str(status)).observe(elapsed)
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            if path not in {"/health/live", "/health/ready", "/metrics"}:
                audit.info(
                    "request",
                    extra={
                        "route": path,
                        "method": request.method,
                        "status": status,
                        "ms": round(elapsed * 1000),
                        "user": user_id_var.get(),
                    },
                )
        response.headers["X-Request-ID"] = rid
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response


def _error(status: int, code: str, message: str, headers: dict[str, str] | None = None, details: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimited) else None
        if exc.status_code >= 500:
            logger.warning("request failed", extra={"code": exc.code, "detail": exc.message[:200]})
            message = exc.public_message  # never leak provider internals
        else:
            message = exc.message
        return _error(exc.status_code, exc.code, message, headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()[:5]]
        return _error(422, "validation_error", "The request is invalid.", details=details)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error", exc_info=exc)
        return _error(500, "internal_error", "Something went wrong. Please try again.")
