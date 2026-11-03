"""Agent 8 — Improver node: generate better hyperparameter variants.

Task E-2: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Task E-3: MLflow experiment logging wired in here.
Spec: .claude/specs/agents/08-improver.md
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import CostLimitExceeded, TokenLimitExceeded
from app.core.state import GraphState
from app.services.cost_guardrail import CostBudgetType, CostGuardrail
from app.services.guardrail_enforcement import (
    enforce_cost_guardrail,
    enforce_token_guardrail,
)
from app.services.mlflow_service import (
    EvalRunMetrics,
    MLflowService,
    PipelineRunParams,
)
from app.services.token_guardrail import TokenBudgetType, TokenGuardrail

_cost_guardrail = CostGuardrail()
_token_guardrail = TokenGuardrail()
_mlflow_service = MLflowService()

logger = logging.getLogger(__name__)

# Baseline config used when state carries no existing variant_config
_DEFAULT_CONFIG: dict[str, Any] = {
    "chunk_strategy": "semantic",
    "chunk_size": 512,
    "child_chunk_size": 128,
    "overlap": 64,
    "k_value": 10,
    "rerank_top_k": 5,
    "embedding_model": "gemini-embedding-2",
    "prompt_template_version": "v1",
}

# Per-failure-type config deltas — generates exactly 3 variants each.
# Numeric values are ADDED to the base; strings REPLACE the base value.
_VARIANT_PLAYBOOK: dict[str, list[dict[str, Any]]] = {
    "F-01": [
        {"k_value": 5, "chunk_size": -50},
        {"chunk_strategy": "hierarchical", "chunk_size": -100},
        {"k_value": 10, "overlap": 32},
    ],
    "F-02": [
        {"k_value": -3, "rerank_top_k": 2},
        {"k_value": -5, "chunk_size": -100},
        {"k_value": -2, "rerank_top_k": 3, "chunk_size": -50},
    ],
    "F-03": [
        {"prompt_template_version": "v2", "chunk_size": -50},
        {"chunk_size": -100, "overlap": 16},
        {"prompt_template_version": "v2", "chunk_size": -150, "overlap": 16},
    ],
    "F-04": [
        {"chunk_size": 200, "overlap": 50},
        {"k_value": 3, "chunk_size": 100},
        {"chunk_size": 300, "overlap": 100, "k_value": 2},
    ],
    "F-05": [
        {"rerank_top_k": -2, "k_value": -3},
        {"k_value": -5},
        {"rerank_top_k": -3, "k_value": -2},
    ],
}

# Deterministic score-delta estimates per failure type (one per variant).
_SCORE_DELTA_ESTIMATES: dict[str, list[float]] = {
    "F-01": [0.06, 0.08, 0.05],
    "F-02": [0.07, 0.05, 0.09],
    "F-03": [0.10, 0.06, 0.12],
    "F-04": [0.07, 0.05, 0.09],
    "F-05": [0.08, 0.06, 0.07],
}


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a GraphState string ID into a UUID, or None if absent/invalid.

    Mirrors evaluator.py's helper of the same name (P0.6-2, 13-Jul-2026) --
    test fixtures and some callers use non-UUID placeholder IDs (e.g.
    "org001"); the cost-guardrail audit write is optional/best-effort on a
    bad ID, not a reason to crash the node.
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _apply_delta(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Return a new config with delta applied. Numerics are summed (min 1); strings replace."""
    result = dict(base)
    for key, val in delta.items():
        if (
            isinstance(val, (int, float))
            and key in result
            and isinstance(result[key], (int, float))
        ):
            result[key] = max(1, result[key] + val)
        else:
            result[key] = val
    return result


def _log_to_mlflow(
    variant_id: str,
    config: dict[str, Any],
    unified_score: float,
    score_delta: float,
    failure_type: str,
    pipeline_id: str,
    x_trace_id: str,
    latency_ms: int = 0,
) -> str:
    """Log one variant run to MLflow via MLflowService. Returns run_id or '' on failure."""
    metrics = EvalRunMetrics(
        unified_score=unified_score,
        cost_per_query_usd=0.0,       # improver generates variants, no direct LLM call
        latency_p95_ms=float(latency_ms),
        total_tokens=0,               # no LLM tokens consumed by improver itself
        llm_provider_used="none",
        score_delta=score_delta,
        failure_type=failure_type,
    )
    params = PipelineRunParams(
        chunk_strategy=str(config.get("chunk_strategy", "semantic")),
        chunk_size=int(config.get("chunk_size", 512)),
        child_chunk_size=int(config.get("child_chunk_size", 128)),
        overlap=int(config.get("overlap", 64)),
        k_value=int(config.get("k_value", 10)),
        rerank_top_k=int(config.get("rerank_top_k", 5)),
        embedding_model=str(config.get("embedding_model", "gemini-embedding-2")),
        prompt_template_version=str(config.get("prompt_template_version", "v1")),
    )
    result = _mlflow_service.log_eval_run(
        pipeline_id=pipeline_id,
        variant_id=variant_id,
        metrics=metrics,
        params=params,
        x_trace_id=x_trace_id,
    )
    return result.run_id


async def improver_node(state: GraphState) -> GraphState:
    """Generate pipeline hyperparameter variants and persist the best to state."""
    start_ms = int(time.monotonic() * 1000)

    x_trace_id: str = state.get("x_trace_id") or ""
    pipeline_id: str = state.get("pipeline_id") or ""
    failure_type: str = state.get("failure_type") or "F-01"
    current_score: float = state.get("unified_score") or 0.0

    base_config: dict[str, Any] = dict(state.get("variant_config") or _DEFAULT_CONFIG)

    # ── E-17: TokenGuardrail — check before expanding chunk_size / context ───
    # P0.6-2 (13-Jul-2026): a breach now actually blocks the run (Rule 86) --
    # previously this silently clamped chunk_size down and continued.
    proposed_prompt_tokens: int = base_config.get("chunk_size", 512) * base_config.get("k_value", 10)
    token_check = _token_guardrail.check(
        requested_tokens=proposed_prompt_tokens,
        budget_type=TokenBudgetType.PROMPT,
        x_trace_id=x_trace_id,
    )
    try:
        enforce_token_guardrail(token_check, node="improver", x_trace_id=x_trace_id)
    except TokenLimitExceeded as exc:
        execution_trace = list(state.get("execution_trace") or [])
        execution_trace.append({
            "node": "improver",
            "timestamp": datetime.now(UTC).isoformat(),
            "x_trace_id": x_trace_id,
            "graph_state_version": state.get("graph_state_version", "v1.0"),
            "latency_ms": int(time.monotonic() * 1000) - start_ms,
            "status": "blocked_token_limit",
            "retry_count": 0,
            "cost_usd": 0.0,
            "provider": "none",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "detail": str(exc),
        })
        return {
            **state,
            "guardrail_blocked": True,
            "guardrail_block_reason": "policy_violation",  # Literal-frozen field (Rule 8); see status="blocked_token_limit" in the trace entry for specifics
            "execution_trace": execution_trace,
        }

    # ── E-16: CostGuardrail — check before generating variants ───────────────
    # P0.6-2 (13-Jul-2026): now writes the Rule 86 Section 10-mandated
    # audit_log row (event_type=cost_limit_exceeded) via the shared helper --
    # previously the block was correct but silent (no audit trail).
    estimated_build_cost: float = 0.003 * 3  # conservative heuristic
    cost_check = _cost_guardrail.check(
        estimated_cost_usd=estimated_build_cost,
        budget_type=CostBudgetType.PIPELINE_BUILD,
        x_trace_id=x_trace_id,
    )
    try:
        await enforce_cost_guardrail(
            cost_check,
            node="improver",
            x_trace_id=x_trace_id,
            organization_id=_safe_uuid(state.get("organization_id")),
            run_id=_safe_uuid(state.get("run_id")),
        )
    except CostLimitExceeded as exc:
        execution_trace = list(state.get("execution_trace") or [])
        execution_trace.append({
            "node": "improver",
            "timestamp": datetime.now(UTC).isoformat(),
            "x_trace_id": x_trace_id,
            "graph_state_version": state.get("graph_state_version", "v1.0"),
            "latency_ms": int(time.monotonic() * 1000) - start_ms,
            "status": "blocked_cost_limit",
            "retry_count": 0,
            "cost_usd": 0.0,
            "provider": "none",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "detail": str(exc),
        })
        return {
            **state,
            "guardrail_blocked": True,
            "guardrail_block_reason": "policy_violation",  # Literal-frozen field (Rule 8); see status="blocked_cost_limit" in the trace entry for specifics
            "execution_trace": execution_trace,
        }

    playbook = _VARIANT_PLAYBOOK.get(failure_type, _VARIANT_PLAYBOOK["F-01"])
    score_deltas = _SCORE_DELTA_ESTIMATES.get(failure_type, _SCORE_DELTA_ESTIMATES["F-01"])

    variants: list[dict[str, Any]] = []
    for i, delta in enumerate(playbook):
        variant_id = str(uuid.uuid4())
        config = _apply_delta(base_config, delta)
        score_delta = score_deltas[i]
        estimated_score = min(1.0, current_score + score_delta)

        mlflow_run_id = _log_to_mlflow(
            variant_id=variant_id,
            config=config,
            unified_score=estimated_score,
            score_delta=score_delta,
            failure_type=failure_type,
            pipeline_id=pipeline_id,
            x_trace_id=x_trace_id,
        )

        variants.append(
            {
                "variant_id": variant_id,
                "config": config,
                "unified_score": estimated_score,
                "score_delta": score_delta,
                "mlflow_run_id": mlflow_run_id,
            }
        )

        logger.info(
            "improver_variant_scored",
            extra={
                "variant_id": variant_id,
                "unified_score": estimated_score,
                "score_delta": score_delta,
                "x_trace_id": x_trace_id,
            },
        )

    best = max(variants, key=lambda item: item["unified_score"])
    latency_ms = int(time.monotonic() * 1000) - start_ms

    logger.info(
        "improver_complete",
        extra={
            "variants_generated": len(variants),
            "best_variant_id": best["variant_id"],
            "best_unified_score": best["unified_score"],
            "failure_type": failure_type,
            "x_trace_id": x_trace_id,
        },
    )

    execution_trace = list(state.get("execution_trace") or [])
    execution_trace.append(
        {
            "node": "improver",
            "timestamp": datetime.now(UTC).isoformat(),
            "x_trace_id": x_trace_id,
            "graph_state_version": state.get("graph_state_version", "v1.0"),
            "latency_ms": latency_ms,
            "status": "success",
            "retry_count": 0,
            "cost_usd": 0.0,
            "provider": "none",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "variant_id": best["variant_id"],
            "mlflow_run_id": best["mlflow_run_id"],
        }
    )

    # Full candidate set (all 3 scored variants, not just the winner) --
    # previously only `best` survived past this function; the other 2 were
    # logged to MLflow and discarded. Persisted verbatim by evaluate.py into
    # agent_execution_metadata.improver_candidates (METRICS_WIRING_MATRIX.md).
    # Not a new GraphState field addition requiring Architecture Review --
    # follows the same untyped-passthrough pattern observer.py already uses
    # for `observation_flags`.
    improver_candidates = [
        {**v, "is_winner": v["variant_id"] == best["variant_id"]} for v in variants
    ]

    return {
        **state,
        "variant_config": best["config"],
        "variant_id": best["variant_id"],
        "improvement_attempt": (state.get("improvement_attempt") or 0) + 1,
        "execution_trace": execution_trace,
        "improver_candidates": improver_candidates,
    }
