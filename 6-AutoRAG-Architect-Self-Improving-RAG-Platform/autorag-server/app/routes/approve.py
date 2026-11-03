"""POST /api/v1/hitl/approve — Submit human-in-the-loop approval or rejection."""

from __future__ import annotations

import uuid
from typing import Literal

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.evaluation_repository import EvaluationRepository

logger = structlog.get_logger(__name__)

router = APIRouter()


class ApprovalRequest(BaseModel):
    """HITL approval/rejection payload."""
    run_id: str
    decision: Literal["approve", "reject"]
    reviewer_note: str = ""


@router.post("")
async def submit_approval(
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Records a human approval or rejection for a pipeline in the 0.70–0.84 score band.
    Generates a signed approval_token that the Deployer Agent validates before proceeding.
    Writes an 'evaluation_approved' or 'evaluation_rejected' audit event.
    """
    org_uuid = uuid.UUID(organization_id)
    run_uuid = uuid.UUID(body.run_id)

    eval_repo = EvaluationRepository(db)
    run = await eval_repo.get_by_run_id(run_id=run_uuid, organization_id=org_uuid)
    if run is None:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "RUN_NOT_FOUND", "message": f"Evaluation run {body.run_id} not found."},
            "request_id": trace_id,
        }

    # Verify the run is actually in the HITL range before accepting approval
    unified_score = run.unified_score or 0.0
    if unified_score >= 0.85:
        return {
            "status": "error",
            "data": None,
            "error": {
                "code": "HITL_NOT_REQUIRED",
                "message": f"Score {unified_score:.3f} >= 0.85; autonomous deploy eligible.",
            },
            "request_id": trace_id,
        }
    if unified_score < 0.70:
        return {
            "status": "error",
            "data": None,
            "error": {
                "code": "SCORE_TOO_LOW",
                "message": f"Score {unified_score:.3f} < 0.70; deploy blocked. Run Diagnoser.",
            },
            "request_id": trace_id,
        }

    # Sign approval token (simple deterministic token — production should use JWT)
    approval_token = str(uuid.uuid5(run_uuid, f"{body.decision}:{current_user.user_id}"))
    new_status = "approved" if body.decision == "approve" else "rejected"

    await eval_repo.update_status(
        run_id=run_uuid,
        organization_id=org_uuid,
        status=new_status,
    )

    event_type = "evaluation_approved" if body.decision == "approve" else "evaluation_rejected"
    audit_repo = AuditLogRepository(db)
    await audit_repo.insert(
        event_type=event_type,
        organization_id=org_uuid,
        run_id=run_uuid,
        payload={
            "decision": body.decision,
            "reviewer": current_user.user_id,
            "reviewer_note": body.reviewer_note,
            "unified_score": unified_score,
            "approval_token": approval_token,
        },
        trace_id=trace_id,
    )
    await db.commit()

    logger.info(
        "hitl.decision_recorded",
        extra={
            "run_id": body.run_id,
            "decision": body.decision,
            "reviewer": current_user.user_id,
            "x_trace_id": trace_id,
        },
    )
    return {
        "status": "ok",
        "data": {
            "run_id": body.run_id,
            "decision": body.decision,
            "approval_token": approval_token if body.decision == "approve" else None,
            "approval_status": new_status,
            "next_step": "deploy" if body.decision == "approve" else "improve",
        },
        "error": None,
        "request_id": trace_id,
    }
