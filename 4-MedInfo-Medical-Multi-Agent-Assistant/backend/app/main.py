"""FastAPI app factory. Run: uvicorn app.main:app --port 8000 (one worker per container)."""

from __future__ import annotations

import hmac
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api import (
    routes_chat,
    routes_conversations,
    routes_documents,
    routes_health,
    routes_review,
    routes_ui_support,
)
from app.api.errors import install_error_handlers
from app.config import get_settings
from app.container import Container, build_container
from app.core.audit import AuditLogger
from app.core.logging import configure_logging, request_id_var
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS

logger = logging.getLogger(__name__)
_NO_AUDIT_ROUTES = {"/healthz", "/readyz", "/metrics", "unmatched"}


def _csp(supabase_url: str) -> str:
    connect = " ".join(x for x in ("'self'", supabase_url) if x)
    return (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
        f"connect-src {connect}; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )


def create_app(container: Container | None = None) -> FastAPI:
    settings = container.settings if container else get_settings()
    configure_logging(settings.log_level, settings.log_format)
    container = container or build_container(settings)

    app = FastAPI(
        title=settings.app_name,
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None,
    )
    app.state.container = container
    csp = _csp(settings.supabase_url)
    audit = AuditLogger(settings.audit_log_enabled)
    metrics_token = settings.metrics_token.get_secret_value() if settings.metrics_token else None

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            elapsed = time.perf_counter() - started
            # Route TEMPLATE (e.g. /api/documents/{doc_id}), never the raw path: bounded label cardinality.
            route = getattr(request.scope.get("route"), "path", "unmatched")
            if route != "/metrics":
                HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
                HTTP_LATENCY.labels(request.method, route).observe(elapsed)
            if route not in _NO_AUDIT_ROUTES and not route.startswith("/static"):
                audit.record(
                    "http.request",
                    user_id=getattr(request.state, "user_id", None),
                    method=request.method,
                    route=route,
                    status=status,
                    duration_ms=round(elapsed * 1000, 1),
                )
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path == "/" or request.url.path.startswith("/static/"):
            # Always revalidate (ETag) so a browser never runs a stale app.js against a newer page.
            response.headers["Cache-Control"] = "no-cache"
        return response

    install_error_handlers(app)
    app.include_router(routes_health.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_documents.admin_router)
    app.include_router(routes_documents.user_router)
    app.include_router(routes_conversations.router)
    app.include_router(routes_review.router)
    app.include_router(routes_review.admin_router)
    app.include_router(routes_ui_support.router)
    app.include_router(routes_ui_support.admin_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> Response:
        """PUBLIC by design for Prometheus scraping, restricted by NetworkPolicy in Kubernetes and, when
        METRICS_TOKEN is set, by a bearer token. Metric labels never contain PHI or free text."""
        if metrics_token is not None:
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(supplied, metrics_token):
                return Response(status_code=401)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    ui_dir = settings.frontend_dir
    if ui_dir is not None and ui_dir.is_dir():
        # Local development only: in containers the frontend (nginx) serves the UI.
        app.mount("/static", StaticFiles(directory=ui_dir), name="static")

        @app.get("/favicon.ico", include_in_schema=False)
        def favicon() -> FileResponse:
            """PUBLIC by design: browsers request it automatically."""
            return FileResponse(ui_dir / "favicon.svg", media_type="image/svg+xml")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            """PUBLIC by design: the UI shell. All data calls behind it require sign-in."""
            return FileResponse(ui_dir / "index.html")

    logger.info("app started", extra={"env": settings.app_env, "model": settings.answer_chain()[0].label})
    return app


@lru_cache(maxsize=1)
def _default_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    # Lazy, cached `app` for uvicorn, so importing this module in tests doesn't read .env or build providers.
    if name == "app":
        return _default_app()
    raise AttributeError(name)
