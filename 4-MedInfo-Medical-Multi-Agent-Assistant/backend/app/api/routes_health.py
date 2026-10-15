"""Health probes. PUBLIC by design (load balancers / kubelet do not authenticate)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.container import Container

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness() -> dict[str, str]:
    """Liveness never checks dependencies: a slow database must not restart the pod."""
    return {"status": "ok"}


@router.get("/readyz")
def readiness(container: Container = Depends(get_container)) -> JSONResponse:
    probe = container.db_probe
    if probe is None:
        # Local/test runs may have no database yet; production requires DATABASE_URL (validated at startup).
        ready = container.settings.app_env != "production"
        return JSONResponse(
            {"status": "ready" if ready else "not_ready", "database": "not_configured"}, 200 if ready else 503
        )
    ok = probe.ping()
    return JSONResponse(
        {"status": "ready" if ok else "not_ready", "database": "ok" if ok else "unreachable"},
        200 if ok else 503,
    )
