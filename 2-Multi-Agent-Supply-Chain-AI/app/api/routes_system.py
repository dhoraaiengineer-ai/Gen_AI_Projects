"""Health, metrics, identity and system status."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.deps import get_services, require_user
from app.container import Services
from app.core.rbac import User
from app.models import schemas as s

health_router = APIRouter(tags=["system"])
router = APIRouter(prefix="/api", tags=["system"])


# Public by design: orchestrators probe these without credentials.
@health_router.get("/health/live")
async def live() -> dict[str, str]:
    """Liveness never checks dependencies — a slow database must not restart healthy pods."""
    return {"status": "ok"}


@health_router.get("/health/ready")
async def ready(response: Response, services: Services = Depends(get_services)) -> dict[str, Any]:
    try:
        await services.db.ping()
        return {"status": "ready"}
    except Exception:
        response.status_code = 503
        return {"status": "not_ready", "database": "unreachable"}


# Public by design but meant to be reachable only inside the cluster (NetworkPolicy / no ingress route).
@health_router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/me", response_model=s.CurrentUser, response_model_by_alias=True)
async def me(user: User = Depends(require_user)) -> s.CurrentUser:
    return s.CurrentUser(id=user.id, email=user.email, name=user.name, role=user.role.value, initials=user.initials)


@router.get("/system/status", response_model=s.SystemStatus, response_model_by_alias=True)
async def system_status(_: User = Depends(require_user), services: Services = Depends(get_services)) -> s.SystemStatus:
    t = time.perf_counter()
    try:
        await services.db.ping()
        db = ("operational", round((time.perf_counter() - t) * 1000))
    except Exception:
        db = ("outage", 0)
    t = time.perf_counter()
    redis_ok = await services.kv.ping() if hasattr(services.kv, "ping") else True
    redis = ("operational" if redis_ok else "degraded", round((time.perf_counter() - t) * 1000))
    breakers = services.breakers.snapshot()
    open_models = [m for m, st in breakers.items() if st == "open"]
    llm = ("degraded" if open_models else "operational", 0)
    services_out = [
        {"name": "API", "status": "operational", "latencyMs": 1},
        {"name": "PostgreSQL", "status": db[0], "latencyMs": db[1]},
        {"name": "Redis", "status": redis[0], "latencyMs": redis[1]},
        {"name": "LLM providers", "status": llm[0], "latencyMs": 0, "detail": ", ".join(open_models)},
        {"name": "Web research", "status": "operational" if services.web else "degraded", "latencyMs": 0},
    ]
    overall = "outage" if db[0] == "outage" else "degraded" if any(x["status"] != "operational" for x in services_out) else "operational"
    env = {"prod": "production", "staging": "staging"}.get(services.settings.env, "development")
    return s.SystemStatus(status=overall, environment=env, version=services.settings.app_version, services=services_out)  # type: ignore[arg-type]


@router.get("/config/public")
async def public_config(services: Services = Depends(get_services)) -> dict[str, str]:
    """Public by design: browser-safe values the UI needs to start sign-in. Never includes secrets."""
    return {"supabaseUrl": services.settings.supabase_url, "supabasePublishableKey": services.settings.supabase_publishable_key}
