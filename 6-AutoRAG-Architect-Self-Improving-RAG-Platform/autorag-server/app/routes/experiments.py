"""GET /api/v1/experiments -- List evaluation runs with score deltas."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.models.evaluation_run import EvaluationRun
from app.repositories.evaluation_repository import EvaluationRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Experiments"])


@router.get("")
async def list_experiments(
    pipeline_id: str | None = Query(default=None, description="Filter by pipeline UUID"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a paginated list of evaluation runs with Unified Score, RAGAS metrics,
    and delta vs. the previous run for the same pipeline.

    Used by the Experiments dashboard to display evaluation history.

    Args:
        pipeline_id: Optional UUID to filter by a specific pipeline.
        limit:        Maximum rows to return (1-100, default 20).
        offset:       Pagination offset (default 0).

    Returns:
        Standard wrapper:
        {
          "status": "ok",
          "data": {
            "experiments": [...],
            "total": <int>,
            "limit": <int>,
            "offset": <int>
          },
          "request_id": "<trace_id>"
        }
    """
    repo = EvaluationRepository(db)
    org_id = uuid.UUID(organization_id)

    if pipeline_id:
        runs = await repo.list_by_pipeline(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=org_id,
            limit=limit,
            offset=offset,
        )
    else:
        runs = await repo.list_by_org(
            organization_id=org_id,
            limit=limit,
            offset=offset,
        )

    # Count total for pagination metadata
    if pipeline_id:
        count_stmt = (
            select(EvaluationRun)
            .where(
                EvaluationRun.organization_id == org_id,
                EvaluationRun.pipeline_id == uuid.UUID(pipeline_id),
            )
        )
    else:
        count_stmt = select(EvaluationRun).where(
            EvaluationRun.organization_id == org_id
        )

    count_result = await db.execute(
        select(text("count(*)")).select_from(count_stmt.subquery())
    )
    total: int = count_result.scalar_one() or 0

    # Compute score delta vs previous run per pipeline
    experiments = []
    prev_score_by_pipeline: dict[str, float | None] = {}

    for run in runs:
        pid = str(run.pipeline_id)
        # unified_score is a SQLAlchemy Numeric column -- asyncpg returns a
        # real decimal.Decimal at runtime regardless of this type hint.
        # Returned unconverted in a plain dict (no Pydantic response_model
        # here), FastAPI's jsonable_encoder serializes Decimal as a JSON
        # *string* ("0.849"), not a number -- silently broke every
        # `.toFixed()` call on the frontend with "not a function" (13-Jul-2026
        # fix; cost_usd below already had this cast, these four didn't).
        current_score: float | None = float(run.unified_score) if run.unified_score is not None else None

        prev_score = prev_score_by_pipeline.get(pid)
        delta: float | None = None
        if current_score is not None and prev_score is not None:
            delta = round(current_score - prev_score, 4)

        prev_score_by_pipeline[pid] = current_score

        experiments.append(
            {
                # run.id is the internal PK; run.run_id is the real external
                # correlation ID every other route (/score/{run_id},
                # /diagnose/{run_id}, /improve/{run_id}) expects -- using
                # run.id here meant any frontend link built from this
                # endpoint's "run_id" would 404 against those routes
                # (Part E fix, 12-Jul-2026).
                "run_id": str(run.run_id),
                "pipeline_id": pid,
                "unified_score": current_score,
                "score_delta": delta,
                "recall": float(run.recall) if run.recall is not None else None,
                "faithfulness": float(run.faithfulness) if run.faithfulness is not None else None,
                # real column is `quality`, not `quality_score` -- the old
                # getattr(..., "quality_score", None) always silently
                # returned None (Part E fix, 12-Jul-2026).
                "quality": float(run.quality) if run.quality is not None else None,
                "latency_p95_ms": float(run.latency_p95_ms) if run.latency_p95_ms is not None else None,
                "cost_usd": float(run.cost_usd) if run.cost_usd is not None else None,
                "status": run.status,
                "created_at": (
                    run.created_at.isoformat() if run.created_at else None
                ),
            }
        )

    logger.info(
        "experiments_listed",
        extra={
            "organization_id": organization_id,
            "pipeline_id": pipeline_id,
            "count": len(experiments),
            "x_trace_id": trace_id,
        },
    )

    return {
        "status": "ok",
        "data": {
            "experiments": experiments,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        "error": None,
        "request_id": trace_id,
    }
