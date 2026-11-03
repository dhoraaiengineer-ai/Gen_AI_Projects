"""GET /api/v1/score/{run_id} — Fetch evaluation results for a completed run."""

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


@router.get("/{run_id}")
async def get_score(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Returns Unified Score, RAGAS metrics, adversarial pass rate, and failure taxonomy
    for a completed evaluation run.
    Status 'pending' or 'running' means the run is still in progress — poll again.
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

    # evaluation_runs.failure_taxonomy is a JSONB *dict* (either the guardrail
    # block shape {"error_type": ...} or, since Part E's fix, the real
    # Diagnoser classification {"failure_type": "F-0X", ...}) -- but the
    # frontend's ScoreResult.failure_taxonomy type is FailureCode[] (every
    # consumer, e.g. RootCausePanel.tsx, does `failure_taxonomy[0]`). Returning
    # the raw dict here meant `[0]` silently evaluated to undefined for every
    # caller of this route. Convert to the real single-item array contract.
    raw_taxonomy = run.failure_taxonomy if isinstance(run.failure_taxonomy, dict) else {}
    failure_code = raw_taxonomy.get("failure_type")
    failure_taxonomy_list: list[str] = [failure_code] if failure_code else []

    ragas_metrics = run.ragas_metrics or {}
    evaluation_mode = ragas_metrics.get("evaluation_mode")  # "FULL" | "DIAGNOSTIC" | None (pre-P0.6 rows)
    recall_at_5_measured = bool(ragas_metrics.get("recall_at_5_measured"))

    data: dict = {
        "run_id": str(run.run_id),
        "pipeline_id": str(run.pipeline_id),
        "status": run.status,
        "dataset_version": run.dataset_version,
        "unified_score": float(run.unified_score) if run.unified_score is not None else None,
        "recall": float(run.recall) if run.recall is not None else None,
        "quality": float(run.quality) if run.quality is not None else None,
        "faithfulness": float(run.faithfulness) if run.faithfulness is not None else None,
        "latency_p95_ms": run.latency_p95_ms,
        "cost_usd": float(run.cost_usd) if run.cost_usd is not None else None,
        # Rule 86 alias — evaluation_runs has no per-run token/provider columns yet
        # (would require a migration); cost_per_query_usd mirrors cost_usd until then.
        "cost_per_query_usd": float(run.cost_usd) if run.cost_usd is not None else None,
        "total_tokens": None,
        "llm_provider_used": None,
        "adversarial_passed": run.adversarial_passed,
        "ragas_metrics": ragas_metrics,
        "failure_taxonomy": failure_taxonomy_list,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        # 12-Jul-2026: real per-node status/timing (Part A/B.1) — powers
        # /dashboard/[id]'s Pipeline Progress view. null for pre-migration-0010
        # rows (older EvaluationRun rows have no agent_execution_metadata).
        "node_trace": (run.agent_execution_metadata or {}).get("node_trace"),
        # P0.6-1/P0.6-3 (13-Jul-2026): FULL when recall_at_5/mrr/ndcg were
        # measured against curated ground truth, DIAGNOSTIC when they're
        # NOT_COLLECTED (see value_types below) — does NOT mean unified_score
        # itself is less trustworthy; its "Recall" input is context_recall,
        # measured every run regardless of ground-truth availability.
        "evaluation_mode": evaluation_mode,
        # Full evidence trail for unified_score — explains "why X" from
        # persisted data alone, no GraphState dependency (P0.6-3).
        "score_provenance": (run.agent_execution_metadata or {}).get("score_provenance"),
        # V4 fast-follow (26-Jul-2026): real GraphState values that were always
        # computed but previously discarded before persistence -- null for
        # rows created before this change. See evaluation_dispatch.py's
        # build_retrieved_context_preview() docstring.
        "retrieved_context_preview": (run.agent_execution_metadata or {}).get(
            "retrieved_context_preview"
        ),
        "generated_answer": (run.agent_execution_metadata or {}).get("generated_answer"),
        # Per-field provenance classification the UI must render explicitly
        # (P0.6-3) — never silently treat NOT_COLLECTED as a measured 0/0.5.
        "value_types": {
            "unified_score": "DERIVED" if run.unified_score is not None else "NOT_COLLECTED",
            "recall": "MEASURED" if run.recall is not None else "NOT_COLLECTED",
            "quality": "MEASURED" if run.quality is not None else "NOT_COLLECTED",
            "faithfulness": "MEASURED" if run.faithfulness is not None else "NOT_COLLECTED",
            "latency_p95_ms": "MEASURED" if run.latency_p95_ms is not None else "NOT_COLLECTED",
            "cost_usd": "MEASURED" if run.cost_usd is not None else "NOT_COLLECTED",
            "recall_at_5": "MEASURED" if recall_at_5_measured else "NOT_COLLECTED",
            "recall_at_10": "MEASURED" if recall_at_5_measured else "NOT_COLLECTED",
            "mrr": "MEASURED" if recall_at_5_measured else "NOT_COLLECTED",
            "ndcg": "MEASURED" if recall_at_5_measured else "NOT_COLLECTED",
        },
    }

    # Surface deployment eligibility alongside score data
    faithfulness = run.faithfulness or 0.0
    unified_score = run.unified_score or 0.0
    adversarial_passed = run.adversarial_passed or False
    if faithfulness < 0.5 or not adversarial_passed:
        data["deployment_gate"] = "blocked"
        data["deployment_gate_reason"] = (
            "faithfulness_below_threshold" if faithfulness < 0.5 else "adversarial_failed"
        )
    elif unified_score >= 0.85:
        data["deployment_gate"] = "eligible"
    elif unified_score >= 0.70:
        data["deployment_gate"] = "hitl_required"
    else:
        data["deployment_gate"] = "blocked"
        data["deployment_gate_reason"] = "score_below_threshold"

    return {"status": "ok", "data": data, "error": None, "request_id": trace_id}
