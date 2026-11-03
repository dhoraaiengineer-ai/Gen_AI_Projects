"""GET /api/v1/runs/{run_id}/metrics — real per-LLM-call agent metrics.

Added 12-Jul-2026 (Part B.0). `agent_metrics` (ADR-006) already captures real
provider/token/cost/latency per LLM call, linked by run_id — nothing exposed
it via any route until now. Cheapest real win in the whole MVP plan: zero new
persistence, just a query + route. See verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.repositories.agent_metrics_repository import AgentMetricsRepository

router = APIRouter()


@router.get("/{run_id}/metrics")
async def get_run_metrics(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Real per-agent LLM call metrics for one evaluation run.

    Returns an empty list (not an error) when no agent in this run made an
    LLM call yet, or the run doesn't exist — callers should treat an empty
    list as "no data available", matching the "Unavailable", not "0" UI rule.
    """
    repo = AgentMetricsRepository(db)
    rows = await repo.list_by_run(
        run_id=uuid.UUID(run_id),
        organization_id=uuid.UUID(organization_id),
    )

    calls = [
        {
            "agent_name": r["agent_name"],
            "provider": r["provider"],
            "prompt_tokens": r["prompt_tokens"],
            "completion_tokens": r["completion_tokens"],
            "total_tokens": r["total_tokens"],
            "cost_usd": float(r["cost_usd"]) if r["cost_usd"] is not None else None,
            "latency_ms": r["latency_ms"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]

    totals = {
        "cost_usd": round(sum(c["cost_usd"] or 0.0 for c in calls), 6) if calls else None,
        "total_tokens": sum(c["total_tokens"] or 0 for c in calls) if calls else None,
        "llm_calls": len(calls),
    }

    return {
        "status": "ok",
        "data": {"run_id": run_id, "calls": calls, "totals": totals},
        "error": None,
        "request_id": trace_id,
    }
