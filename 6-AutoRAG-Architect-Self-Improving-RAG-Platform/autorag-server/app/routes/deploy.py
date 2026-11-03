"""Deploy namespace routes -- /api/v1/deploy/*.

Mounted by routes/api.py with prefix="/deploy", then app.main mounts the whole
api_router at settings.api_v1_prefix ("/api/v1"). This router MUST NOT declare
its own "/api/v1/deploy" prefix -- APIRouter prefixes concatenate on include,
they do not replace, so a self-prefix here would double up to
"/api/v1/deploy/api/v1/deploy/...". Matches the pipelines.py / audit_log.py /
jobs.py convention (no self-prefix; the parent supplies the full path).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_organization_id, get_trace_id
from app.core.exceptions import DeploymentBlockedError, PipelineNotFoundError
from app.db.session import get_db
from app.services.deployment_service import DeploymentService

router = APIRouter(tags=["Deployment"])


class DeployRequest(BaseModel):
    """POST /api/v1/deploy/{run_id} -- request body."""

    task_arn: str
    approval_token: str | None = None


class DeployResponse(BaseModel):
    """Deployment initiation response."""

    status: str
    data: dict
    request_id: str


class RollbackRequest(BaseModel):
    """POST /api/v1/deploy/rollback -- request body."""

    pipeline_id: str
    rollback_reason: str = "Manual emergency rollback"


class PromoteRequest(BaseModel):
    """POST /api/v1/deploy/promote -- request body."""

    pipeline_id: str


@router.post("/rollback", response_model=DeployResponse)
async def rollback_deployment(
    body: RollbackRequest,
    x_trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Manually trigger ALB weight swap back to the Blue (previous) task ARN.

    Frozen contract path (CLAUDE.md section 11): POST /api/v1/deploy/rollback.
    Auto-rollback (error_rate > 1%, p95 > 3s, score drop > 0.10) is handled
    by the Observer Agent canary monitor within the 10-minute canary window.
    This endpoint is for manual emergency rollback triggered from the
    Deployment Center UI (E-12) or by Lead DevOps.

    Owner: Team 1 (DevOps) / Team 2 (Deployer Agent)
    Spec: .claude/specs/agents/09-deployer.md section Rollback
    """
    svc = DeploymentService(db)

    try:
        result = await svc.rollback(
            pipeline_id=body.pipeline_id,
            organization_id=organization_id,
            rollback_reason=body.rollback_reason,
            x_trace_id=x_trace_id,
        )
    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "pipeline_not_found", "message": str(exc), "request_id": x_trace_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(exc), "request_id": x_trace_id},
        ) from exc

    return DeployResponse(status="ok", data=result, request_id=x_trace_id)


@router.post("/promote", response_model=DeployResponse)
async def promote_deployment(
    body: PromoteRequest,
    x_trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Promote the active Blue/Green canary to 100% Green (production).

    Called once the canary window has passed health checks. Transitions the
    latest 'blue_green' deployment row to 'promoted'.

    Owner: Team 2 / Team 10
    Spec: .claude/specs/agents/09-deployer.md
    """
    svc = DeploymentService(db)

    try:
        result = await svc.promote(
            pipeline_id=body.pipeline_id,
            organization_id=organization_id,
            x_trace_id=x_trace_id,
        )
    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "pipeline_not_found", "message": str(exc), "request_id": x_trace_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(exc), "request_id": x_trace_id},
        ) from exc

    return DeployResponse(status="ok", data=result, request_id=x_trace_id)


@router.get("/history", response_model=DeployResponse)
async def deployment_history(
    pipeline_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    x_trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """List deployment history for a pipeline, newest first (Deployment Center — Chapter 24)."""
    svc = DeploymentService(db)
    result = await svc.get_history(
        pipeline_id=pipeline_id,
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    return DeployResponse(status="ok", data=result, request_id=x_trace_id)


@router.get("/status", response_model=DeployResponse)
async def deployment_status(
    pipeline_id: str = Query(...),
    x_trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Return the most recent deployment (any status) for a pipeline — live BlueGreenBar polling."""
    svc = DeploymentService(db)
    result = await svc.get_current_status(
        pipeline_id=pipeline_id,
        organization_id=organization_id,
    )
    return DeployResponse(status="ok", data=result, request_id=x_trace_id)


# NOTE: this path-parameter route MUST be registered last among the POST
# handlers in this router -- FastAPI matches routes in registration order,
# so a POST /{run_id} declared before /rollback or /promote would swallow
# those literal paths as run_id="rollback" / run_id="promote".
@router.post("/{run_id}", response_model=DeployResponse)
async def deploy_pipeline(
    run_id: str,
    body: DeployRequest,
    x_trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Trigger a Blue/Green ECS Fargate deployment for a completed evaluation run.

    Gate check order (non-bypassable per CLAUDE.md section 9):
      1. faithfulness >= 0.5  (hard block -- overrides everything including HITL)
      2. adversarial_passed == True  (hard block)
      3. unified_score >= 0.85  (autonomous)  OR  score in [0.70, 0.85) + approval_token  (HITL)
      4. score < 0.70  (hard block -- Improver loop required)

    Returns 200 with deploy_status="blue_green" on success.
    Returns 422 with DeploymentBlockedError details on any gate failure.

    Owner: Team 2 / Team 10
    Spec: .claude/specs/agents/09-deployer.md
    """
    svc = DeploymentService(db)

    try:
        result = await svc.deploy(
            run_id=run_id,
            organization_id=organization_id,
            task_arn=body.task_arn,
            approval_token=body.approval_token,
            x_trace_id=x_trace_id,
        )
    except DeploymentBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "deployment_blocked",
                "message": exc.reason,
                "unified_score": exc.score,
                "request_id": x_trace_id,
            },
        ) from exc
    except PipelineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "pipeline_not_found", "message": str(exc), "request_id": x_trace_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(exc), "request_id": x_trace_id},
        ) from exc

    return DeployResponse(status="ok", data=result, request_id=x_trace_id)
