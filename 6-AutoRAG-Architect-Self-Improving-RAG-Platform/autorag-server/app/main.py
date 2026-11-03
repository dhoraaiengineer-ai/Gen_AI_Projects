"""
AutoRAG Architect — FastAPI Application Entry Point
Version: 3.0.0

Start with:
    uv run uvicorn app.main:app --reload

Production:
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging
import sys
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from starlette.responses import Response

from app.core.config import settings
from app.core.workflow import create_workflow_with_checkpointer
from app.routes.api import api_router

# ─────────────────────────────────────────────────────────────
# Stdlib Logging Configuration
# ─────────────────────────────────────────────────────────────
# Every LangGraph node module uses `logging.getLogger(__name__)` (stdlib),
# separate from the structlog-based route-level loggers. Without this call
# the root logger has no handler and defaults to WARNING, so every node's
# INFO-level progress log (parse/chunk/embed steps) is silently dropped --
# a Rule 85 violation that makes production debugging blind. structlog's
# own ConsoleRenderer output is unaffected by this.
logging.basicConfig(
    level=logging.DEBUG if settings.is_local else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

# ─────────────────────────────────────────────────────────────
# Startup Validation + LangGraph Checkpointer Init
# ─────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _required = {
        "DATABASE_URL": settings.database_url,
        "SUPABASE_URL": settings.supabase_url,
        "GEMINI_API_KEY": settings.gemini_api_key,
    }
    missing = [k for k, v in _required.items() if not v]
    if missing and settings.environment != "local":
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Set them in .env or AWS Secrets Manager before starting."
        )

    # Wire AsyncPostgresSaver (falls back to MemorySaver if SUPABASE_DB_URL unset)
    async with create_workflow_with_checkpointer() as workflow:
        app.state.workflow = workflow

        # Seed default org for local demo so X-Organization-ID header resolves in DB.
        # Idempotent: ON CONFLICT DO NOTHING makes restarts safe.
        if settings.environment == "local":
            from sqlalchemy import text

            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as _db:
                await _db.execute(
                    text(
                        "INSERT INTO organizations (id, name, slug) "
                        "VALUES (:id, :name, :slug) ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "name": "Local Dev Organization",
                        "slug": "local-dev",
                    },
                )
                # Seed a default pipeline so ConfiguratorWizard.listProjects() returns a usable ID
                await _db.execute(
                    text(
                        "INSERT INTO pipelines (id, organization_id, name, status, embedding_model) "
                        "VALUES (:id, :org_id, :name, :status, :model) ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": "01960000-0000-7000-8000-000000000001",
                        "org_id": "00000000-0000-0000-0000-000000000001",
                        "name": "Local Demo Pipeline",
                        "status": "ready",
                        "model": "gemini-embedding-2",
                    },
                )
                # Seed the local auth-bypass user (app/auth/dependencies.py) so FK
                # columns that reference users.id (e.g. documents.uploaded_by) resolve.
                await _db.execute(
                    text(
                        "INSERT INTO users (id, organization_id, email, full_name, role) "
                        "VALUES (:id, :org_id, :email, :full_name, :role) ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "org_id": "00000000-0000-0000-0000-000000000001",
                        "email": "dev@local",
                        "full_name": "Local Dev User",
                        "role": "admin",
                    },
                )
                await _db.commit()

        yield


# ─────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="🛡️ AutoRAG Architect",
    description=(
        "Production-grade autonomous RAG platform — "
        "9-agent LangGraph orchestration with enterprise guardrails."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────
# CORS Middleware
# ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    # PATCH added 16-Jul-2026 -- first PATCH route (finalize_pipeline,
    # draft -> pending) was silently failing on the browser's CORS preflight
    # (OPTIONS request rejected before the real PATCH ever fired) because it
    # was missing here. No prior route used PATCH so this went unnoticed.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID", "X-Request-ID"],
)

# ─────────────────────────────────────────────────────────────
# X-Trace-ID Middleware — echo or generate on every response
# ─────────────────────────────────────────────────────────────


@app.middleware("http")
async def trace_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response


# ─────────────────────────────────────────────────────────────
# Central API Router
# ─────────────────────────────────────────────────────────────

app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)

# ─────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────

Instrumentator().instrument(app).expose(app)

# ─────────────────────────────────────────────────────────────
# Standard Response Wrapper
# ─────────────────────────────────────────────────────────────


def ok(data: object, request_id: str = "") -> dict[str, Any]:
    """Standard success response envelope."""

    return {
        "status": "ok",
        "data": data,
        "error": None,
        "request_id": request_id,
    }


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────


@app.get(
    "/health",
    tags=["Operational"],
    summary="Container health probe",
)
async def health_check() -> dict[str, Any]:
    """
    Health endpoint for:
    - Docker
    - ECS
    - ALB
    - Kubernetes
    - monitoring systems
    """

    return ok(
        {
            "service": "autorag-server",
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "healthy",
        }
    )


# ─────────────────────────────────────────────────────────────
# Agent Execution Endpoint — wired to LangGraph graph
# ─────────────────────────────────────────────────────────────


class AgentQuery(BaseModel):
    query: str
    pipeline_id: str
    organization_id: str
    stream: bool = False
    session_id: str | None = None
    user_id: str | None = None


@app.post(
    "/api/v1/agent/query",
    tags=["Agent Execution"],
)
async def execute_agent_loop(
    payload: AgentQuery,
    request: Request,
) -> dict[str, Any]:
    """Execute the 9-agent AutoRAG LangGraph loop for a query.

    Initialises GraphState via initial_state(), invokes the compiled graph
    (stored on app.state.workflow from lifespan), and returns the final state's
    key fields as the response.

    For HITL pipelines (score 0.70-0.84), the graph pauses at the hitl node
    and returns status="pending_approval" with the run_id for polling.

    Returns HTTP 202 + job_id when the graph is running asynchronously.
    """
    from app.core.database import AsyncSessionLocal
    from app.core.state import format_pipeline_version, initial_state
    from app.repositories.pipeline_repository import PipelineRepository

    trace_id = request.headers.get("X-Trace-ID", "") or str(uuid.uuid4())

    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    run_id = str(uuid.uuid4())
    session_id = payload.session_id or str(uuid.uuid4())
    user_id = payload.user_id or "anonymous"

    # 20-Jul-2026 (Version 4): resolve the pipeline's REAL current_version --
    # pipeline_chunks (migration 0016) filters by this exact string, so a
    # missing lookup here would silently dispatch against "v1" regardless of
    # how many times the pipeline has actually been re-versioned.
    pipeline_version = format_pipeline_version(1)
    try:
        async with AsyncSessionLocal() as pv_db:
            pipeline_row = await PipelineRepository(pv_db).get_by_id(
                pipeline_id=uuid.UUID(payload.pipeline_id),
                organization_id=uuid.UUID(payload.organization_id),
            )
        if pipeline_row is not None:
            pipeline_version = format_pipeline_version(pipeline_row.current_version)
    except ValueError:
        pass  # invalid UUID -- fall through with the v1 default, same as before this fix

    state = initial_state(
        run_id=run_id,
        pipeline_id=payload.pipeline_id,
        organization_id=payload.organization_id,
        x_trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        raw_query=payload.query.strip(),
        pipeline_version=pipeline_version,
    )

    workflow = getattr(request.app.state, "workflow", None)
    if workflow is None:
        raise HTTPException(status_code=503, detail="Agent workflow not initialised.")

    config = {"configurable": {"thread_id": run_id}}

    try:
        final_state: dict[str, Any] = await workflow.ainvoke(state, config=config)
    except Exception as exc:
        # GraphInterrupt from HITL node surfaces as an exception here --
        # that is expected: the graph paused, checkpoint was saved, return 202.
        exc_class = type(exc).__name__
        if "GraphInterrupt" in exc_class or "interrupt" in str(exc).lower():
            return ok(
                {
                    "status": "pending_approval",
                    "run_id": run_id,
                    "message": "Pipeline score requires human approval. "
                               "Awaiting reviewer decision.",
                },
                request_id=trace_id,
            )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ok(
        {
            "run_id": run_id,
            "status": final_state.get("deploy_status") or "completed",
            "query": payload.query,
            "rewritten_query": final_state.get("rewritten_query"),
            "generated_answer": final_state.get("generated_answer"),
            "unified_score": final_state.get("unified_score"),
            "faithfulness": final_state.get("faithfulness"),
            "deploy_status": final_state.get("deploy_status"),
            "pipeline_id": payload.pipeline_id,
            "organization_id": payload.organization_id,
        },
        request_id=trace_id,
    )


# ─────────────────────────────────────────────────────────────
# Global Exception Handler
# ─────────────────────────────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """
    Normalizes every HTTPException (raised anywhere in the app) into the
    standard {status, data, error, request_id} envelope (API_SPEC.md v1.1),
    so apiClient's generic error extraction (envelope.error?.message) always
    surfaces the real message instead of falling back to "HTTP {status}".

    `detail` may be a plain string (FastAPI default) or a dict with
    error/message keys (this codebase's common pattern) — both are handled.
    """
    trace_id = request.headers.get("X-Trace-ID", "")
    detail = exc.detail

    if isinstance(detail, dict):
        code = str(detail.get("code") or detail.get("error") or "HTTP_ERROR").upper()
        message = str(detail.get("message") or detail)
        error_body: dict[str, Any] = {"code": code, "message": message}
        extra = {k: v for k, v in detail.items() if k not in ("code", "error", "message", "request_id")}
        if extra:
            error_body["details"] = extra
    else:
        error_body = {"code": "HTTP_ERROR", "message": str(detail)}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "data": None,
            "error": error_body,
            "request_id": trace_id,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Prevents internal stack traces from leaking externally.
    """

    trace_id = request.headers.get("X-Trace-ID", "")

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            },
            "request_id": trace_id,
        },
    )


# ─────────────────────────────────────────────────────────────
# Development Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
