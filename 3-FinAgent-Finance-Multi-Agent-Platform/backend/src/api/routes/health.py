"""Health probes.

PUBLIC BY DESIGN: probes answer without a token so Docker, Kubernetes and load balancers can call
them. They return status only — no data, no versions, no error details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.deps import get_container
from src.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

CHECK_TIMEOUT_SECONDS = 3.0


@router.get("")
async def live() -> dict[str, str]:
    """Liveness: the process is up and serving requests."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(container: Annotated[Container, Depends(get_container)]) -> JSONResponse:
    """Readiness: every dependency answers within the timeout."""
    results: dict[str, str] = {}
    for name, check in container.health_checks.items():
        try:
            await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
            results[name] = "ok"
        except Exception as exc:
            logger.warning(
                "readiness check failed", extra={"check": name, "error": type(exc).__name__}
            )
            results[name] = "unavailable"
    ok = all(v == "ok" for v in results.values())
    return JSONResponse(
        {"status": "ok" if ok else "unavailable", "checks": results}, status_code=200 if ok else 503
    )
