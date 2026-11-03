"""GET /api/v1/diagnose/{run_id} — Return failure taxonomy from a completed evaluation run."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.repositories.evaluation_repository import EvaluationRepository

logger = structlog.get_logger(__name__)

router = APIRouter()


# Failure type taxonomy — corrected 12-Jul-2026 to match the real taxonomy in
# app/graph/nodes/diagnoser.py (this dict previously had 5 entries that didn't
# match F-01..F-05's actual meanings there at all, and was missing F-06).
_FAILURE_DESCRIPTIONS: dict[str, str] = {
    "F-01": "Retrieval Miss — retrieved chunks are empty or all low-score.",
    "F-02": "Context Overflow — context was truncated due to token budget.",
    "F-03": "Hallucination — faithfulness < 0.5, generated answer contains fabricated facts.",
    "F-04": "Answer Incompleteness — low unified_score but faithfulness OK, missing information.",
    "F-05": "Latency Spike — p95 response time exceeds 3s SLO.",
    "F-06": "Quality Drift — sustained multi-run score decline (G-6), not a single acute drop.",
}


@router.get("/{run_id}")
async def get_diagnosis(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Returns failure root-cause classification (F-01..F-06), confidence, and
    remediation hints for a completed evaluation run.
    If the run has not yet reached the Diagnoser node, failure_type will be null.
    """
    repo = EvaluationRepository(db)
    run = await repo.get_by_run_id(
        run_id=uuid.UUID(run_id),
        organization_id=uuid.UUID(organization_id),
    )
    if run is None:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "RUN_NOT_FOUND", "message": f"Evaluation run {run_id} not found."},
            "request_id": trace_id,
        }

    raw_taxonomy = run.failure_taxonomy
    failure_taxonomy: dict = raw_taxonomy if isinstance(raw_taxonomy, dict) else {}
    failure_type = failure_taxonomy.get("failure_type")
    confidence = failure_taxonomy.get("confidence")
    remediation_hint = failure_taxonomy.get("remediation_hint")
    root_cause_analysis = failure_taxonomy.get("root_cause_analysis")

    return {
        "status": "ok",
        "data": {
            "run_id": run_id,
            "pipeline_id": str(run.pipeline_id),
            "status": run.status,
            "unified_score": float(run.unified_score) if run.unified_score is not None else None,
            "failure_type": failure_type,
            "failure_description": _FAILURE_DESCRIPTIONS.get(failure_type, "") if failure_type else None,
            "confidence": confidence,
            "remediation_hint": remediation_hint,
            "root_cause_analysis": root_cause_analysis,
            "ragas_metrics": run.ragas_metrics or {},
        },
        "error": None,
        "request_id": trace_id,
    }
