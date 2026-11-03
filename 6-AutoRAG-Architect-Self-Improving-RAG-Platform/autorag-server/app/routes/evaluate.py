"""POST /api/v1/evaluate — Start 3-layer evaluation loop and return job_id."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.exceptions import PipelineNotFoundError
from app.core.state import format_pipeline_version, initial_state
from app.repositories.evaluation_repository import EvaluationRepository
from app.schemas.evaluation import EvaluationRequest
from app.services.evaluation_dispatch import run_and_persist_evaluation
from app.services.ground_truth_service import (
    default_golden_path_question,
    is_golden_path_document,
)
from app.services.pipeline_service import PipelineService
from app.services.vector_service import VectorService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("")
async def start_evaluation(
    body: EvaluationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Dispatches a full 3-layer evaluation run (Unified Score + RAGAS + Adversarial).
    Creates an evaluation_run DB row, dispatches LangGraph as a background task.
    Returns job_id for polling via GET /api/v1/jobs/{job_id}.

    query resolution (P0.5-1, 12-Jul-2026): `body.query` is used verbatim if
    provided. Otherwise, this pipeline's ingested chunks are checked against
    the golden-path demo document fixture (`ground_truth_service.py`) — if it
    matches, a real curated question is used (dataset-driven mode). If
    neither applies, the request is rejected with 422 rather than silently
    dispatching an empty query that would hard-block Evaluator on
    faithfulness=0.0 without ever reaching Observer/Diagnoser/Improver.
    """
    from app.main import app  # avoid circular import at module load

    # 20-Jul-2026 (Version 4): pipeline_version must reflect the pipeline's
    # REAL current_version, not a hardcoded default -- pipeline_chunks
    # (migration 0016) filters by this value, so an evaluation dispatched
    # against the wrong version string would silently see zero/stale chunks.
    try:
        pipeline_row = await PipelineService(db).get_by_id(
            pipeline_id=body.pipeline_id, organization_id=organization_id
        )
        pipeline_version = format_pipeline_version(pipeline_row["current_version"])
    except PipelineNotFoundError:
        pipeline_version = format_pipeline_version(1)

    resolved_query = (body.query or "").strip()
    if not resolved_query:
        is_golden_path = await is_golden_path_document(
            vector_service=VectorService(db=db),
            pipeline_id=body.pipeline_id,
            pipeline_version=pipeline_version,
            organization_id=organization_id,
        )
        if is_golden_path:
            resolved_query = default_golden_path_question().query
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "missing_query",
                    "message": (
                        "A non-empty 'query' is required to evaluate this pipeline. "
                        "Dataset-driven evaluation (no query needed) is only "
                        "available for the golden-path demo document."
                    ),
                    "request_id": trace_id,
                },
            )

    run_id = uuid.uuid4()
    eval_repo = EvaluationRepository(db)

    # Create pending evaluation_run row so /jobs/{id} can report status
    await eval_repo.create(
        pipeline_id=uuid.UUID(body.pipeline_id),
        organization_id=uuid.UUID(organization_id),
        run_id=run_id,
        dataset_version=body.dataset_version,
        status="pending",
    )
    await db.commit()

    # 20-Jul-2026 (Apply Improvement feature): seed variant_config from the
    # pipeline's active version config, if one was ever set (e.g. via
    # apply-improvement). None for every pipeline that's never had a config
    # applied -- graph nodes fall back to their existing hardcoded defaults
    # exactly as before this existed, so this is additive, not a behavior
    # change for pipelines that don't use the new feature.
    try:
        active_config = await PipelineService(db).get_active_config(
            pipeline_id=body.pipeline_id, organization_id=organization_id
        )
    except PipelineNotFoundError:
        # Enrichment only -- the pipeline_id was already validated by the
        # eval_repo.create() FK insert above; this can't legitimately fail
        # here, but if it ever does, fall back to no seeded config rather
        # than failing a request that's otherwise already committed.
        active_config = None

    state = initial_state(
        run_id=str(run_id),
        pipeline_id=body.pipeline_id,
        organization_id=organization_id,
        x_trace_id=trace_id,
        user_id=current_user.user_id,
        session_id=str(uuid.uuid4()),
        raw_query=resolved_query,
        pipeline_version=pipeline_version,
        variant_config=active_config,
    )
    background_tasks.add_task(run_and_persist_evaluation, state, app.state)

    logger.info(
        "evaluation.dispatched",
        extra={"run_id": str(run_id), "pipeline_id": body.pipeline_id, "x_trace_id": trace_id},
    )
    return {
        "status": "ok",
        "data": {
            "run_id": str(run_id),
            "job_id": str(run_id),
            "pipeline_id": body.pipeline_id,
            "dataset_version": body.dataset_version,
            "message": "Evaluation dispatched; poll /api/v1/jobs/{job_id} for status.",
        },
        "error": None,
        "request_id": trace_id,
    }


@router.get("/history")
async def list_evaluation_history(
    pipeline_id: str = Query(...),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """List past evaluation runs for a pipeline, newest first."""
    repo = EvaluationRepository(db)
    runs = await repo.list_by_pipeline(
        pipeline_id=uuid.UUID(pipeline_id),
        organization_id=uuid.UUID(organization_id),
        limit=limit,
        offset=offset,
    )
    items = [
        {
            "run_id": str(r.run_id),
            "status": r.status,
            "unified_score": float(r.unified_score) if r.unified_score is not None else None,
            "faithfulness": float(r.faithfulness) if r.faithfulness is not None else None,
            "adversarial_passed": r.adversarial_passed,
            "dataset_version": r.dataset_version,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]
    return {
        "status": "ok",
        "data": {"items": items, "limit": limit, "offset": offset},
        "error": None,
        "request_id": trace_id,
    }
