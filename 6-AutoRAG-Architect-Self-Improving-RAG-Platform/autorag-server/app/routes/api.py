"""Central API router aggregation."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import get_trace_id
from app.routes import (
    approve,
    audit_log,
    batch_evaluations,
    configurator,
    deploy,
    diagnose,
    documents,
    evaluate,
    evaluation_datasets,
    experiments,
    improve,
    ingest,
    jobs,
    marketing,
    observe,
    pipelines,
    projects,
    query,
    retrieve,
    runs,
    score,
)

api_router = APIRouter()


# ─────────────────────────────────────────────────────────────
# /api/v1/health — deep health with dependency probes
# ─────────────────────────────────────────────────────────────


@api_router.get("/health", tags=["Operational"], summary="Deep health check")
async def api_health(trace_id: str = Depends(get_trace_id)) -> JSONResponse:
    """
    Deep health check — probes DB and Redis connectivity.
    Returns 200 when all critical dependencies are reachable.
    Returns 503 when any dependency is unavailable.
    """

    from app.core.config import settings

    checks: dict[str, str] = {}

    # DB probe
    try:
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unreachable"

    # Redis probe
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()  # type: ignore[attr-defined]  # aclose() missing from types-redis 4.6 stub
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unreachable"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    body = {
        "status": "ok" if all_ok else "degraded",
        "data": {
            "service": "autorag-server",
            "version": settings.app_version,
            "environment": settings.environment,
            "checks": checks,
        },
        "error": None,
        "request_id": trace_id,
    }
    return JSONResponse(content=body, status_code=status_code)


# ─────────────────────────────────────────────────────────────
# Public Marketing Routes (no auth, no organization scoping)
# ─────────────────────────────────────────────────────────────

api_router.include_router(
    marketing.router,
    prefix="/marketing",
    tags=["Marketing"],
)

# ─────────────────────────────────────────────────────────────
# Core Platform Routes
# ─────────────────────────────────────────────────────────────

api_router.include_router(
    pipelines.router,
    prefix="/pipelines",
    tags=["Pipelines"],
)

api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"],
)

api_router.include_router(
    evaluate.router,
    prefix="/evaluate",
    tags=["Evaluation"],
)

api_router.include_router(
    experiments.router,
    prefix="/experiments",
    tags=["Experiments"],
)

api_router.include_router(
    audit_log.router,
    prefix="/audit-log",
    tags=["Audit Log"],
)

# ─────────────────────────────────────────────────────────────
# AI Platform Routes
# ─────────────────────────────────────────────────────────────

api_router.include_router(
    configurator.router,
    prefix="/configurator",
    tags=["Configurator"],
)

api_router.include_router(
    ingest.router,
    prefix="/ingest",
    tags=["Ingestion"],
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)

api_router.include_router(
    query.router,
    prefix="/query",
    tags=["Query"],
)

api_router.include_router(
    retrieve.router,
    prefix="/retrieve",
    tags=["Retrieval"],
)

# ─────────────────────────────────────────────────────────────
# Deployment Routes
# ─────────────────────────────────────────────────────────────

api_router.include_router(
    deploy.router,
    prefix="/deploy",
    tags=["Deployment"],
)

api_router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["Jobs"],
)

api_router.include_router(
    approve.router,
    prefix="/hitl/approve",
    tags=["HITL"],
)

api_router.include_router(
    score.router,
    prefix="/score",
    tags=["Evaluation"],
)

api_router.include_router(
    diagnose.router,
    prefix="/diagnose",
    tags=["Diagnosis"],
)

api_router.include_router(
    improve.router,
    prefix="/improve",
    tags=["Improvement"],
)

api_router.include_router(
    observe.router,
    prefix="/observe",
    tags=["Observer"],
)

api_router.include_router(
    runs.router,
    prefix="/runs",
    tags=["Runs"],
)

# ─────────────────────────────────────────────────────────────
# Evaluation Center Routes (Version 4.1)
# ─────────────────────────────────────────────────────────────

api_router.include_router(
    evaluation_datasets.router,
    prefix="/evaluation-datasets",
    tags=["Evaluation Datasets"],
)

api_router.include_router(
    batch_evaluations.router,
    prefix="/batch-evaluations",
    tags=["Batch Evaluations"],
)
