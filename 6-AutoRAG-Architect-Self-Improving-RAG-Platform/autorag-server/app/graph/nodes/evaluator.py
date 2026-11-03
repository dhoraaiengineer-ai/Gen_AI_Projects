"""Agent 5 — Evaluator node: 3-layer evaluation stack (D-16).

Evaluation layers (executed in order):
  1. Answer Generation — LLM generates answer from compressed_context + query
  2. RAGAS Metrics    — 4 original + 5 extended = 9 total metrics
  3. Adversarial Gate — 10-question hallucination benchmark (100% pass required)
  4. Unified Score    — weighted formula gate (>= 0.85 for autonomous deploy)

Hard blocks (non-bypassable — evaluator-standards.md Rule 6 + Rule 7):
  - faithfulness < 0.5      → guardrail_blocked = True, guardrail_block_reason = "hallucination"
  - adversarial_pass_rate < 1.0 → guardrail_blocked = True, guardrail_block_reason = "hallucination"

HITL gate (evaluator-standards.md Rule 4):
  - 0.70 <= unified_score < 0.85 → approval_required = True

Rule 60:  Must be async def, stateless, read/write only owned GraphState fields.
Rule 86:  x_trace_id in every log line. Cost tracked via LLMService only.
Rule 70:  Inputs (query, context) must be PII-masked — enforced at ingestion boundary.
Spec:     .claude/specs/agents/05-evaluator.md
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from jinja2 import Template

from app.core.database import AsyncSessionLocal
from app.core.exceptions import EvaluationFailedError
from app.core.state import GraphState
from app.metrics import ORG_ADVERSARIAL_PASS_RATE, ORG_SCORE_AVG
from app.services.adversarial_service import AdversarialService
from app.services.evaluation_service import EvaluationService
from app.services.ground_truth_service import resolve_relevant_ids
from app.services.llm_service import LLMResponse, LLMService
from app.services.ragas_service import RAGASService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Answer generation prompt — v1.0
# Used when generated_answer is not already present in GraphState.
# ─────────────────────────────────────────────────────────────────────────────

_ANSWER_GENERATION_PROMPT_V1 = Template(
    """\
You are a precise document Q&A assistant. Prompt version: v1.0

Context (retrieved from the knowledge base):
{{ context }}

Question: {{ query }}

Instructions:
- Answer based ONLY on the Context above.
- If the Context does not contain enough information to answer, respond:
  "I don't have enough information in the provided context to answer this question."
- Be concise, accurate, and grounded.
- Do not invent facts if the context is empty or insufficient.\
"""
)


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a GraphState string ID into a UUID, or None if absent/invalid.

    Used to pass organization_id/run_id through to LLMService.call() so
    agent_metrics actually gets rows (12-Jul-2026) -- these are optional on
    the LLMService side, so a bad/missing value degrades to "no metrics row"
    rather than failing the whole evaluation.
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def evaluator_node(state: GraphState) -> GraphState:
    """Run the 3-layer evaluation stack and update GraphState.

    Owned output fields (graph-state-governance.md Rule 2):
        generated_answer, unified_score, ragas_metrics, faithfulness,
        adversarial_pass_rate, latency_p95_ms, cost_per_query_usd,
        guardrail_blocked, guardrail_block_reason, approval_required,
        llm_provider_used, execution_trace
    """
    node_start = time.monotonic()
    x_trace_id: str = state.get("x_trace_id", "")
    existing_trace: list[dict[str, Any]] = list(state.get("execution_trace", []))

    logger.info(
        "Evaluator node started",
        extra={
            "x_trace_id": x_trace_id,
            "run_id": state.get("run_id", ""),
            "pipeline_id": state.get("pipeline_id", ""),
        },
    )

    llm_service = LLMService()
    ragas_service = RAGASService(llm_service)
    adversarial_service = AdversarialService(llm_service)
    eval_service = EvaluationService()

    # Accumulated cost + tokens across all LLM calls in this node
    total_cost_usd = 0.0
    total_tokens = 0
    llm_provider_used: str = state.get("llm_provider_used") or "gemini-flash-3.5"

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Generate answer (if not already in state from a previous node)
    # ─────────────────────────────────────────────────────────────────────────
    answer: str = (state.get("generated_answer") or "").strip()
    answer_llm_response: LLMResponse | None = None

    if not answer:
        compressed_context = state.get("compressed_context") or ""
        query = state.get("rewritten_query") or state.get("raw_query", "")

        if not query:
            return _blocked_state(
                state=state,
                existing_trace=existing_trace,
                x_trace_id=x_trace_id,
                node_start=node_start,
                reason="policy_violation",
                detail="No query in GraphState — cannot generate answer.",
            )

        generation_prompt = _ANSWER_GENERATION_PROMPT_V1.render(
            context=compressed_context, query=query
        )
        logger.info(
            "Generating answer via LLMService",
            extra={"x_trace_id": x_trace_id, "context_len": len(compressed_context)},
        )

        try:
            answer_llm_response = await llm_service.call(
                prompt=generation_prompt,
                x_trace_id=x_trace_id,
                agent_name="evaluator",
                max_tokens=1024,
                organization_id=_safe_uuid(state.get("organization_id")),
                run_id=_safe_uuid(state.get("run_id")),
            )
        except Exception as exc:
            logger.error(
                "Answer generation failed",
                extra={"x_trace_id": x_trace_id, "error": str(exc)},
            )
            return _blocked_state(
                state=state,
                existing_trace=existing_trace,
                x_trace_id=x_trace_id,
                node_start=node_start,
                reason="policy_violation",
                detail=f"LLM answer generation failed: {exc}",
            )

        answer = answer_llm_response.content.strip()
        total_cost_usd += answer_llm_response.cost_usd
        total_tokens += answer_llm_response.total_tokens
        llm_provider_used = answer_llm_response.provider

    logger.info(
        "Answer available for evaluation",
        extra={"x_trace_id": x_trace_id, "answer_len": len(answer)},
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Build context strings from retrieved chunks
    # ─────────────────────────────────────────────────────────────────────────
    # `chunk_text` is the real field name written by builder.py -- `content`/
    # `text`/`page_content` are defensive fallbacks only (P0.5, 12-Jul-2026: this
    # mismatch previously made context_texts silently empty on every real run,
    # driving faithfulness/context_recall/context_precision to a hard 0.0
    # regardless of actual retrieval quality -- see compressor.py's identical fix).
    retrieved_chunks: list[dict[str, Any]] = list(state.get("retrieved_chunks", []))
    context_texts: list[str] = [
        str(c.get("chunk_text") or c.get("content") or c.get("text") or c.get("page_content") or "")
        for c in retrieved_chunks
        if c.get("chunk_text") or c.get("content") or c.get("text") or c.get("page_content")
    ]
    query_for_eval = state.get("rewritten_query") or state.get("raw_query", "")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Compute 5 original RAGAS metrics (LLM-as-judge)
    # ─────────────────────────────────────────────────────────────────────────
    # 24-Jul-2026 (Evaluation Center, Phase 2): batch_eval_service.py seeds
    # ground_truth/relevant_chunk_ids into variant_config -- the existing
    # free-form dict field ingestion.py/builder.py already read chunk_strategy
    # and retrieval params from -- rather than adding a new GraphState field
    # (graph-state-governance.md Rule 8 would require Architecture Review for
    # that). A standard POST /evaluate dispatch has no variant_config.ground_truth,
    # so answer_correctness stays correctly None for those runs, exactly as
    # before this change.
    variant_config: dict[str, Any] = state.get("variant_config") or {}
    seeded_ground_truth: str | None = variant_config.get("ground_truth") or None
    seeded_relevant_ids: list[str] | None = variant_config.get("relevant_chunk_ids") or None

    logger.info("Computing RAGAS metrics", extra={"x_trace_id": x_trace_id})
    try:
        ragas_scores, ragas_reasoning = await ragas_service.compute_ragas(
            query=query_for_eval,
            answer=answer,
            context_chunks=context_texts,
            ground_truth=seeded_ground_truth,
            x_trace_id=x_trace_id,
            organization_id=_safe_uuid(state.get("organization_id")),
            run_id=_safe_uuid(state.get("run_id")),
        )
    except EvaluationFailedError as exc:
        logger.error(
            "RAGAS computation failed",
            extra={"x_trace_id": x_trace_id, "error": str(exc)},
        )
        return _blocked_state(
            state=state,
            existing_trace=existing_trace,
            x_trace_id=x_trace_id,
            node_start=node_start,
            reason="policy_violation",
            detail=f"RAGAS evaluation failed: {exc}",
        )

    # compute_ragas's return type is dict[str, float | None] because
    # answer_correctness alone can be None (no ground truth) -- faithfulness
    # is always computed unconditionally (see ragas_service.compute_ragas),
    # so this narrows the type at the one call site that actually needs a
    # non-Optional float, rather than loosening every downstream signature.
    _faithfulness_raw = ragas_scores["faithfulness"]
    assert _faithfulness_raw is not None, "faithfulness is always computed by compute_ragas"
    faithfulness: float = _faithfulness_raw

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Compute 5 extended IR metrics (pure math — no LLM)
    # ─────────────────────────────────────────────────────────────────────────
    # 19-Jul-2026 fix: this used to read state.get("latency_p95_ms"), but no
    # upstream node (query_rewriter/builder/compressor) ever writes that field --
    # it stays GraphState's initial None forever, so `or 0` silently zeroed the
    # Unified Score formula's -0.10×Latency term on every run (live-confirmed:
    # two real evaluation runs both persisted latency_p95_ms=0/NULL). node_start
    # (captured at function entry) already gives a real, measured elapsed time
    # covering the dominant per-query cost -- answer generation + RAGAS judging
    # (Steps 1-3 above) -- so use that instead of a phantom always-empty field.
    retrieval_latency_ms: int = int((time.monotonic() - node_start) * 1000)

    # Part A.1 (12-Jul-2026): real ground truth for the golden-path demo
    # document only -- resolve_relevant_ids returns None for every other
    # pipeline. P0.6-1 (13-Jul-2026): ragas_service now returns None (not a
    # fabricated 0.5) for mrr/ndcg/recall_at_5/recall_at_10 when
    # relevant_ids is None -- see all_ragas_metrics.evaluation_mode below.
    # 24-Jul-2026: a batch-evaluation golden_question's own
    # relevant_chunk_ids (curated by a human reviewer, seeded via
    # variant_config -- see seeded_relevant_ids above) is real ground truth
    # too and takes priority over the golden-path lookup, which only
    # recognizes one hardcoded demo document.
    relevant_ids: list[str] | None = seeded_relevant_ids
    if relevant_ids is None:
        try:
            async with AsyncSessionLocal() as gt_db:
                relevant_ids = await resolve_relevant_ids(
                    vector_service=VectorService(db=gt_db),
                    pipeline_id=state.get("pipeline_id") or "",
                    pipeline_version=state.get("pipeline_version") or "v1",
                    organization_id=state.get("organization_id") or "",
                    query=state.get("raw_query") or "",
                )
        except Exception as exc:
            logger.warning(
                "ground_truth_lookup_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

    extended_scores = ragas_service.compute_extended_metrics(
        retrieved_chunks=retrieved_chunks,
        relevant_ids=relevant_ids,
        search_latency_ms=retrieval_latency_ms,
    )

    # Merge all 9 metrics into a single dict. `recall_at_5_measured` records
    # provenance: True only when real ground truth was resolved (Part A.1,
    # golden-path demo document). P0.6-1 (13-Jul-2026): when False,
    # recall_at_5/recall_at_10/mrr/ndcg are now None (NOT_COLLECTED), never a
    # fabricated 0.5 — see ragas_service.compute_extended_metrics.
    #
    # `evaluation_mode` — FULL when the 4 ranking metrics above were genuinely
    # measured against curated ground truth; DIAGNOSTIC otherwise (RAGAS,
    # faithfulness, latency, cost, and adversarial results are still fully
    # real and exposed in DIAGNOSTIC mode — only the ranking-ground-truth
    # metrics are unavailable). This does NOT gate unified_score: the
    # formula's "Recall" input (Step 6 below) is RAGAS context_recall, an
    # LLM-judged metric computed from the query/context/answer on every run
    # regardless of ground-truth availability — not recall_at_5. Unified
    # Score is therefore a fully-measured value in both modes; DIAGNOSTIC
    # only means "don't trust this run's recall_at_5 ranking metric," not
    # "don't trust unified_score."
    all_ragas_metrics: dict[str, Any] = {
        **ragas_scores,
        **extended_scores,
        "recall_at_5_measured": relevant_ids is not None,
        "evaluation_mode": "FULL" if relevant_ids is not None else "DIAGNOSTIC",
    }
    # Judge reasoning (V4 fast-follow, 26-Jul-2026) -- only added when at
    # least one real reasoning string exists, to avoid a noisy empty key on
    # every run (e.g. runs with no ground truth never get answer_correctness
    # reasoning).
    if ragas_reasoning:
        all_ragas_metrics["reasoning"] = ragas_reasoning

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Run adversarial hallucination benchmark (10 questions)
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("Running adversarial benchmark", extra={"x_trace_id": x_trace_id})
    try:
        adversarial_result = await adversarial_service.run_benchmark(
            x_trace_id=x_trace_id,
            context=state.get("compressed_context") or "",
            organization_id=_safe_uuid(state.get("organization_id")),
            run_id=_safe_uuid(state.get("run_id")),
        )
    except EvaluationFailedError as exc:
        logger.error(
            "Adversarial benchmark failed",
            extra={"x_trace_id": x_trace_id, "error": str(exc)},
        )
        return _blocked_state(
            state=state,
            existing_trace=existing_trace,
            x_trace_id=x_trace_id,
            node_start=node_start,
            reason="policy_violation",
            detail=f"Adversarial benchmark failed to run: {exc}",
        )

    adversarial_pass_rate: float = adversarial_result["pass_rate"]

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Compute Unified Score
    # Formula: 0.25×Recall + 0.35×Quality + 0.25×Faithfulness − 0.10×L − 0.05×C
    #
    # "Recall" (24-Jul-2026, v1.2): a blended Retrieval sub-score via
    # compute_retrieval_score() (ContextPrecision + ContextRecall), not raw
    # context_recall alone. Still LLM-judged, always real — NOT recall_at_5
    # (the ground-truth-dependent IR ranking metric, None/NOT_COLLECTED in
    # DIAGNOSTIC mode). Do not substitute recall_at_5 here — that would be
    # exactly the placeholder-into-the-gate-score bug P0.6-1 ruled out.
    #
    # "Quality" (24-Jul-2026, v1.2): a blend of AnswerCorrectness +
    # AnswerRelevancy via compute_quality_score() — deliberately excludes
    # ContextPrecision/ContextRecall (those live in Retrieval above) so no
    # RAGAS metric is double-counted across the two sub-scores. See
    # compute_quality_score() for the answer_correctness=None fallback.
    # Faithfulness remains its own independent top-level term, unchanged.
    # ─────────────────────────────────────────────────────────────────────────
    _recall_raw = ragas_scores["context_recall"]
    _relevancy_raw = ragas_scores["answer_relevancy"]
    _precision_raw = ragas_scores["context_precision"]
    assert _recall_raw is not None, "context_recall is always computed by compute_ragas"
    assert _relevancy_raw is not None, "answer_relevancy is always computed by compute_ragas"
    assert _precision_raw is not None, "context_precision is always computed by compute_ragas"
    recall: float = eval_service.compute_retrieval_score(
        context_precision=_precision_raw,
        context_recall=_recall_raw,
    )
    quality: float = eval_service.compute_quality_score(
        answer_relevancy=_relevancy_raw,
        answer_correctness=ragas_scores["answer_correctness"],
    )
    cost_usd: float = (state.get("cost_per_query_usd") or 0.0) + total_cost_usd

    unified_score = eval_service.compute_unified_score(
        recall=recall,
        quality=quality,
        faithfulness=faithfulness,
        latency_p95_ms=retrieval_latency_ms,
        cost_usd=cost_usd,
    )

    # R-051 fix (24-Jul-2026 release audit): real Prometheus exposition of
    # the score just computed above, so the UnifiedScoreDrop alert rule
    # (observability/alerts/autorag-alerts.yml) has an actual metric to
    # query -- previously it referenced a metric name that never existed
    # anywhere in this codebase and could never fire.
    _org_id_for_metric = state.get("organization_id")
    if _org_id_for_metric:
        ORG_SCORE_AVG.labels(organization_id=str(_org_id_for_metric)).set(unified_score)
        # R-049 fix (24-Jul-2026 release audit): same real-exposition pattern
        # as ORG_SCORE_AVG above, for the Grafana "Adversarial Pass Rate" panel.
        ORG_ADVERSARIAL_PASS_RATE.labels(organization_id=str(_org_id_for_metric)).set(
            adversarial_pass_rate
        )

    # P0.6-3 (13-Jul-2026): persisted evidence trail — score.py must be able
    # to explain unified_score from stored data alone, without GraphState.
    score_provenance = eval_service.build_score_provenance(
        recall=recall,
        quality=quality,
        faithfulness=faithfulness,
        latency_p95_ms=retrieval_latency_ms,
        cost_usd=cost_usd,
        unified_score=unified_score,
        evaluation_mode=all_ragas_metrics["evaluation_mode"],
    )
    # Threaded through ragas_metrics (a real GraphState field) rather than new
    # top-level GraphState keys -- same "extend the existing JSONB, don't grow
    # the frozen contract" pattern as recall_at_5_measured/evaluation_mode
    # above and agent_execution_metadata (migration 0010). evaluate.py reads
    # these back out to populate evaluation_runs.recall/quality (real
    # columns, previously never written) and agent_execution_metadata.
    all_ragas_metrics["recall"] = recall
    all_ragas_metrics["quality"] = quality
    all_ragas_metrics["score_provenance"] = score_provenance

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Determine deployment gate — hard blocks + HITL routing
    # evaluator-standards.md Rules 3–7 + ai-guardrails.md Rules 5, 8
    # ─────────────────────────────────────────────────────────────────────────
    gate, approval_required = eval_service.get_deployment_gate(
        unified_score=unified_score,
        faithfulness=faithfulness,
        adversarial_pass_rate=adversarial_pass_rate,
    )

    if gate == "hard_block":
        logger.warning(
            "HARD BLOCK: deployment gate blocked",
            extra={
                "x_trace_id": x_trace_id,
                "faithfulness": faithfulness,
                "adversarial_pass_rate": adversarial_pass_rate,
                "unified_score": unified_score,
                "failures": adversarial_result.get("failures", []),
            },
        )
        node_latency_ms = int((time.monotonic() - node_start) * 1000)
        trace_entry = _build_trace_entry(
            x_trace_id=x_trace_id,
            state=state,
            latency_ms=node_latency_ms,
            status="blocked",
            llm_response=answer_llm_response,
        )
        return {
            **state,
            "generated_answer": answer,
            "faithfulness": faithfulness,
            "adversarial_pass_rate": adversarial_pass_rate,
            "ragas_metrics": all_ragas_metrics,
            "unified_score": unified_score,
            "guardrail_blocked": True,
            "guardrail_block_reason": "hallucination",
            "approval_required": False,
            "execution_trace": [*existing_trace, trace_entry],
            "adversarial_failures": adversarial_result.get("failures", []),
        }

    logger.info(
        "Deployment gate evaluated",
        extra={
            "x_trace_id": x_trace_id,
            "unified_score": unified_score,
            "gate": gate,
            "approval_required": approval_required,
        },
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: MLflow telemetry (Rule 86 §6 — mandatory)
    # ─────────────────────────────────────────────────────────────────────────
    await eval_service.log_to_mlflow(
        unified_score=unified_score,
        faithfulness=faithfulness,
        context_recall=recall,
        mrr=extended_scores["mrr"],
        ndcg=extended_scores["ndcg"],
        recall_at_5=extended_scores["recall_at_5"],
        recall_at_10=extended_scores["recall_at_10"],
        # search_latency_ms is always real (never None -- only the 4
        # ground-truth-dependent ranking metrics can be NOT_COLLECTED); the
        # `or 0.0` is a type narrowing no-op, not a fallback that can fire.
        search_latency_ms=extended_scores["search_latency_ms"] or 0.0,
        cost_per_query_usd=cost_usd,
        latency_p95_ms=float(retrieval_latency_ms),
        total_tokens=total_tokens,
        evaluation_mode=all_ragas_metrics["evaluation_mode"],
        llm_provider=llm_provider_used,
        run_name=f"eval-{state.get('run_id', 'unknown')[:8]}",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: Build execution_trace entry (graph-state-governance.md Rule 5)
    # ─────────────────────────────────────────────────────────────────────────
    node_latency_ms = int((time.monotonic() - node_start) * 1000)
    trace_entry = _build_trace_entry(
        x_trace_id=x_trace_id,
        state=state,
        latency_ms=node_latency_ms,
        status="success",
        llm_response=answer_llm_response,
    )

    logger.info(
        "Evaluator node completed",
        extra={
            "x_trace_id": x_trace_id,
            "unified_score": unified_score,
            "faithfulness": faithfulness,
            "adversarial_pass_rate": adversarial_pass_rate,
            "approval_required": approval_required,
            "latency_ms": node_latency_ms,
        },
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 10: Return updated GraphState (owned fields only — Rule 2)
    # ─────────────────────────────────────────────────────────────────────────
    return {
        **state,
        "generated_answer": answer,
        "unified_score": unified_score,
        "ragas_metrics": all_ragas_metrics,
        "faithfulness": faithfulness,
        "adversarial_pass_rate": adversarial_pass_rate,
        "latency_p95_ms": retrieval_latency_ms,
        "cost_per_query_usd": cost_usd,
        "approval_required": approval_required,
        "guardrail_blocked": False,
        "guardrail_block_reason": None,
        "llm_provider_used": llm_provider_used,  # type: ignore[typeddict-item]
        "execution_trace": [*existing_trace, trace_entry],
        "adversarial_failures": adversarial_result.get("failures", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_trace_entry(
    *,
    x_trace_id: str,
    state: GraphState,
    latency_ms: int,
    status: str,
    llm_response: LLMResponse | None,
) -> dict[str, Any]:
    """Build a Rule 5 compliant execution_trace entry for the evaluator node."""
    entry: dict[str, Any] = {
        "node": "evaluator",
        "timestamp": datetime.now(UTC).isoformat(),
        "x_trace_id": x_trace_id,
        "graph_state_version": state.get("graph_state_version", "v1.0"),
        "latency_ms": latency_ms,
        "status": status,
        "retry_count": state.get("retry_count") or 0,
    }
    # Cost fields populated by LLMService only (Rule 86 §2)
    if llm_response is not None:
        entry["cost_usd"] = llm_response.cost_usd
        entry["provider"] = llm_response.provider
        entry["prompt_tokens"] = llm_response.prompt_tokens
        entry["completion_tokens"] = llm_response.completion_tokens
    else:
        entry["cost_usd"] = 0.0
        entry["provider"] = state.get("llm_provider_used") or "gemini-flash-3.5"
        entry["prompt_tokens"] = 0
        entry["completion_tokens"] = 0
    return entry


def _blocked_state(
    *,
    state: GraphState,
    existing_trace: list[dict[str, Any]],
    x_trace_id: str,
    node_start: float,
    reason: str,
    detail: str,
) -> GraphState:
    """Return a guardrail-blocked GraphState with a failed trace entry."""
    node_latency_ms = int((time.monotonic() - node_start) * 1000)
    trace_entry = _build_trace_entry(
        x_trace_id=x_trace_id,
        state=state,
        latency_ms=node_latency_ms,
        status="failed",
        llm_response=None,
    )
    logger.error(
        "Evaluator node blocked",
        extra={"x_trace_id": x_trace_id, "reason": reason, "detail": detail},
    )
    return {
        **state,
        "guardrail_blocked": True,
        "guardrail_block_reason": reason,  # type: ignore[typeddict-item]
        "approval_required": False,
        "unified_score": 0.0,
        "faithfulness": state.get("faithfulness", 0.0),
        "adversarial_pass_rate": state.get("adversarial_pass_rate", 0.0),
        "ragas_metrics": state.get("ragas_metrics", {}),
        # 19-Jul-2026: same latency fix as the main path -- record real elapsed
        # time on the blocked path too, instead of leaving latency_p95_ms unset.
        "latency_p95_ms": node_latency_ms,
        "execution_trace": [*existing_trace, trace_entry],
    }
