"""Kubernetes-style probes.

- /health/live:  the process is up. Never checks dependencies, so a DB outage doesn't
                 make Kubernetes restart every pod.
- /health/ready: dependencies are reachable; failing removes the pod from load balancing.
"""

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_container
from app.container import Container
from app.models.schemas import LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
def live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}})
def ready(response: Response, container: Container = Depends(get_container)) -> ReadinessResponse:
    checks = {name: check() for name, check in container.readiness_checks.items()}
    ok = all(checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ok" if ok else "unavailable", checks=checks)
