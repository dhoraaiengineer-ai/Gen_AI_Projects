"""GET /api/v1/jobs/{job_id} — Poll LangGraph job status via evaluation_run or Redis."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.repositories.evaluation_repository import EvaluationRepository

router = APIRouter()


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Poll the status of a long-running LangGraph job (evaluation, ingestion, deployment).
    job_id corresponds to the run_id returned by /ingest or /evaluate.
    Status values: 'pending' | 'running' | 'completed' | 'failed' | 'blocked' | 'pending_approval'
    """
    # job_id maps to evaluation_run.run_id (correlation ID from LangGraph)
    try:
        run_uuid = uuid.UUID(job_id)
    except ValueError:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "INVALID_JOB_ID", "message": f"Invalid job_id format: {job_id}"},
            "request_id": trace_id,
        }

    # Check evaluation_runs table first
    eval_repo = EvaluationRepository(db)
    run = await eval_repo.get_by_run_id(
        run_id=run_uuid,
        organization_id=uuid.UUID(organization_id),
    )

    if run is not None:
        is_terminal = run.status in ("completed", "blocked", "failed")
        # pending_approval runs have a real, persisted score (evaluator already
        # ran) -- only Deployer hasn't run yet, awaiting POST /approve/{run_id}.
        has_score = run.status in ("completed", "blocked", "pending_approval")
        result = {"score_url": f"/api/v1/score/{job_id}"} if has_score else None
        job_error = (
            {"code": "EVALUATION_FAILED", "message": "The evaluation workflow failed. See failure_taxonomy in score details."}
            if run.status == "failed"
            else None
        )
        return {
            "status": "ok",
            "data": {
                "job_id": job_id,
                "status": run.status,
                "pipeline_id": str(run.pipeline_id),
                "result": result,
                "error": job_error,
                "started_at": run.created_at.isoformat() if run.created_at else None,
                "finished_at": run.updated_at.isoformat() if is_terminal and run.updated_at else None,
            },
            "error": None,
            "request_id": trace_id,
        }

    # Fallback: check Redis for ingestion/other job types not tracked in eval_runs
    try:
        import json

        import redis.asyncio as aioredis

        from app.core.config import settings

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(f"job:{job_id}")
        await r.aclose()  # type: ignore[attr-defined]
        if raw:
            job_data = json.loads(raw)
            return {
                "status": "ok",
                "data": {"job_id": job_id, **job_data},
                "error": None,
                "request_id": trace_id,
            }
    except Exception:
        pass  # Redis lookup is best-effort

    return {
        "status": "error",
        "data": None,
        "error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found."},
        "request_id": trace_id,
    }
