"""FastAPI application factory."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    admin,
    appointments,
    auth,
    chat,
    diagnosis,
    documents,
    health,
    repair_orders,
    vehicles,
    warranty,
    workflow,
)
from app.core.config import get_settings
from app.core.errors import HTTP_STATUS_CODES, DomainError
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, get_request_id
from app.schemas.envelope import Envelope

log = structlog.get_logger("app")


def _error(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:  # type: ignore[type-arg]
    body = Envelope[None].fail(code, message, get_request_id(request), details)
    return JSONResponse(body.model_dump(mode="json"), status_code=status)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="AutoServe AI", version="0.1.0", docs_url="/docs", redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID", "traceparent"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _error(request, exc.http_status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return _error(request, 400, "VALIDATION_ERROR", "Request validation failed.", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_STATUS_CODES.get(exc.status_code, "INTERNAL_ERROR")
        message = "Not found." if exc.status_code == 404 else str(exc.detail)
        return _error(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error_type=type(exc).__name__)
        return _error(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")

    for router in (
        health.router,
        auth.router,
        vehicles.router,
        repair_orders.router,
        appointments.router,
        chat.router,
        documents.router,
        diagnosis.router,
        workflow.router,
        warranty.router,
        admin.router,
    ):
        app.include_router(router)
    return app


app = create_app()
