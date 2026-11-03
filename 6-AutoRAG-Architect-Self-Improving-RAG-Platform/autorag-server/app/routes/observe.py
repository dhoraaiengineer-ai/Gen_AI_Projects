"""GET /api/v1/observe -- Real Observer signals for a pipeline.

Added 12-Jul-2026 (Part B.2). observer_node genuinely computes error_rate,
quality_trend, alert_triggered, and observation_flags (incl. quality_drift)
every run -- previously computed then discarded, never exposed via any route,
and the frontend faked equivalent-looking output by re-aggregating
GET /score/{run_id} client-side. This route returns the real, server-computed
signals from the most recent run, plus a short real score history.

Per the 12-Jul-2026 UI provenance rule: if fewer than the requested history
window of runs exist, report the real count -- never pad with synthetic runs.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.repositories.evaluation_repository import EvaluationRepository

router = APIRouter()

_HISTORY_WINDOW = 7


@router.get("")
async def get_observer_view(
    pipeline_id: str = Query(..., description="Pipeline UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Real Observer signals for a pipeline: latest run's computed signals
    plus real score history (up to the last 7 completed runs -- fewer if
    fewer exist; never a fabricated 7-run trend).
    """
    repo = EvaluationRepository(db)
    org_id = uuid.UUID(organization_id)
    runs = await repo.list_by_pipeline(
        pipeline_id=uuid.UUID(pipeline_id),
        organization_id=org_id,
        limit=_HISTORY_WINDOW,
    )

    if not runs:
        return {
            "status": "ok",
            "data": {
                "pipeline_id": pipeline_id,
                "latest_run_id": None,
                "signals": None,
                "history": [],
                "history_note": "No evaluation runs yet for this pipeline.",
            },
            "error": None,
            "request_id": trace_id,
        }

    latest = runs[0]
    metadata = latest.agent_execution_metadata or {}
    signals = metadata.get("observer_signals")

    history = [
        {
            "run_id": str(r.run_id),
            "unified_score": float(r.unified_score) if r.unified_score is not None else None,
            "cost_usd": float(r.cost_usd) if r.cost_usd is not None else None,
            "latency_p95_ms": r.latency_p95_ms,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]

    history_note = (
        None
        if len(runs) >= _HISTORY_WINDOW
        else f"Insufficient history for a full {_HISTORY_WINDOW}-run trend — only {len(runs)} run(s) exist."
    )

    return {
        "status": "ok",
        "data": {
            "pipeline_id": pipeline_id,
            "latest_run_id": str(latest.run_id),
            # null when the latest run never reached Observer (e.g. blocked
            # earlier in the graph) -- do not fabricate signals for it.
            "signals": signals,
            "history": history,
            "history_note": history_note,
        },
        "error": None,
        "request_id": trace_id,
    }
