"""Maps domain errors to HTTP: quota -> 429, provider error -> 502, unavailable -> 503."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def _app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if exc.status_code == 429:
            headers["Retry-After"] = str(exc.retry_after or 60)
        logger.warning("request failed", extra={"error": type(exc).__name__, "status": exc.status_code})
        return JSONResponse(
            {"detail": exc.detail, "error": type(exc).__name__}, exc.status_code, headers=headers
        )

    @app.exception_handler(Exception)
    def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Pass the exception explicitly: inside an exception handler sys.exc_info() may already be cleared,
        # which would log "NoneType: None" and hide the cause.
        logger.error(
            "unhandled error",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"error": type(exc).__name__},
        )
        return JSONResponse({"detail": "Internal error. Please try again."}, 500)
