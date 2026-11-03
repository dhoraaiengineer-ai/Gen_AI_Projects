"""Business logic for evaluation runs — Unified Score, RAGAS, Adversarial gate.

Rule 86 mandatory: Every evaluation run logs 11 MLflow metrics + 1 param.
Rule 50: Unified Score formula is frozen — 0.25R + 0.35Q + 0.25F - 0.10L - 0.05C.
Rule evaluator-standards.md §3: Faithfulness < 0.5 and adversarial_pass_rate < 1.0
  are hard deployment blocks. No override possible.

D-15 + D-16 merged:
  - compute_unified_score(): pure math, input validation, no side effects
  - get_deployment_gate(): 4-gate routing oracle (D-15 design)
  - log_to_mlflow(): Rule 86 §6 telemetry (D-16 addition)

Spec: .claude/specs/agents/05-evaluator.md
"""
from __future__ import annotations

import logging
from typing import Any

import mlflow

from app.core.config import settings
from app.core.exceptions import EvaluationFailedError

logger = logging.getLogger(__name__)

# Unified Score formula weights — FROZEN CONTRACT (evaluator-standards.md §11)
# Changing these requires Architecture Review.
_W_RECALL = 0.25
_W_QUALITY = 0.35
_W_FAITHFULNESS = 0.25
_W_LATENCY = 0.10
_W_COST = 0.05

# Normalization reference points for penalty factors
_LATENCY_MAX_MS = 3_000.0   # 3 s = maximum acceptable p95 latency (SLO target)
_FAITHFULNESS_HARD_BLOCK = 0.5   # non-bypassable (evaluator-standards.md Rule 6)

# Bump whenever _W_* weights or the normalization formula change (P0.6-3,
# 13-Jul-2026) -- persisted alongside every score so a historical run's
# unified_score can always be explained/reproduced from its stored inputs,
# even if the formula is later revised.
UNIFIED_SCORE_FORMULA_VERSION = "v1.2"

# Retrieval sub-formula weights (24-Jul-2026) -- makes "Recall" a true
# composite retrieval score instead of raw context_recall alone.
_RW_PRECISION = 0.5
_RW_RECALL = 0.5

# Quality sub-formula weights (24-Jul-2026, v1.2) -- blends 2 of the 5
# original RAGAS metrics into the single "Quality" input the frozen Unified
# Score formula above expects. History: v1.0 had Quality = answer_relevancy
# alone. v1.1 blended in context_precision/context_recall/answer_correctness,
# but that double-counted context_precision/context_recall (they were also
# the top-level "Recall" input). v1.2 fixes this: Quality is now purely a
# generation-quality signal (AnswerCorrectness + AnswerRelevancy),
# Retrieval is now purely a retrieval signal (ContextPrecision +
# ContextRecall, see compute_retrieval_score() below), and Faithfulness
# stays its own independent top-level term -- no metric is counted twice.
# The top-level Unified Score formula and its weights are UNCHANGED (still
# 0.25R + 0.35Q + 0.25F - 0.10L - 0.05C).
_QW_CORRECTNESS = 0.6
_QW_RELEVANCY = 0.4


class EvaluationService:
    """Orchestrates the 3-layer evaluation stack.

    Called by the evaluator LangGraph node. Not called directly by API routes —
    routes enqueue evaluation jobs and poll /api/v1/jobs/{id}.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Public: Retrieval sub-score (24-Jul-2026) — pure computation, no side effects
    # ─────────────────────────────────────────────────────────────────────────

    def compute_retrieval_score(
        self,
        *,
        context_precision: float,
        context_recall: float,
    ) -> float:
        """Blend context_precision and context_recall into the "Recall" input
        compute_unified_score() expects (named "Recall" in the frozen top-level
        formula for historical reasons; represents overall retrieval quality).

        Formula (all inputs 0.0-1.0):
            Retrieval = 0.5*ContextPrecision + 0.5*ContextRecall

        Both inputs are always real RAGAS metrics (never None) -- unlike
        answer_correctness, no fallback is needed here.
        """
        if not (0.0 <= context_precision <= 1.0):
            raise ValueError("context_precision must be between 0.0 and 1.0")
        if not (0.0 <= context_recall <= 1.0):
            raise ValueError("context_recall must be between 0.0 and 1.0")

        retrieval = round(
            min(max(_RW_PRECISION * context_precision + _RW_RECALL * context_recall, 0.0), 1.0),
            4,
        )

        logger.info(
            "Retrieval sub-score computed",
            extra={
                "retrieval": retrieval,
                "context_precision": context_precision,
                "context_recall": context_recall,
            },
        )
        return retrieval

    # ─────────────────────────────────────────────────────────────────────────
    # Public: Quality sub-score (24-Jul-2026) — pure computation, no side effects
    # ─────────────────────────────────────────────────────────────────────────

    def compute_quality_score(
        self,
        *,
        answer_relevancy: float,
        answer_correctness: float | None,
    ) -> float:
        """Blend answer_correctness and answer_relevancy into the single
        "Quality" input the frozen Unified Score formula expects.

        Formula (all inputs 0.0-1.0):
            Quality = 0.6*AnswerCorrectness + 0.4*AnswerRelevancy

        A pure generation-quality signal -- deliberately excludes
        context_precision/context_recall (those are the "Retrieval" input,
        see compute_retrieval_score()) so no RAGAS metric is counted twice
        across the two sub-scores.

        answer_correctness is None whenever a run has no real ground truth
        (the common case -- see evaluator.py's seeded_ground_truth handling).
        When None, Quality collapses to answer_relevancy alone (weight 1.0)
        rather than treating the missing metric as 0 (which would silently
        penalize every ungrounded run) or substituting a fabricated value.
        """
        if not (0.0 <= answer_relevancy <= 1.0):
            raise ValueError("answer_relevancy must be between 0.0 and 1.0")
        if answer_correctness is not None and not (0.0 <= answer_correctness <= 1.0):
            raise ValueError("answer_correctness must be between 0.0 and 1.0 when provided")

        if answer_correctness is None:
            quality = answer_relevancy
        else:
            quality = _QW_CORRECTNESS * answer_correctness + _QW_RELEVANCY * answer_relevancy

        quality = round(min(max(quality, 0.0), 1.0), 4)

        logger.info(
            "Quality sub-score computed",
            extra={
                "quality": quality,
                "answer_relevancy": answer_relevancy,
                "answer_correctness": answer_correctness,
            },
        )
        return quality

    # ─────────────────────────────────────────────────────────────────────────
    # Public: Unified Score (frozen formula) — pure computation, no side effects
    # ─────────────────────────────────────────────────────────────────────────

    def compute_unified_score(
        self,
        *,
        recall: float,
        quality: float,
        faithfulness: float,
        latency_p95_ms: int | float,
        cost_usd: float,
    ) -> float:
        """Compute the Unified Score using the frozen weighted formula.

        Formula (evaluator-standards.md §1 + CLAUDE.md §9):
            Score = 0.25×Recall + 0.35×Quality + 0.25×Faithfulness
                    − 0.10×Latency_norm − 0.05×Cost_norm

        Latency_norm = min(latency_p95_ms / 3000, 1.0)  — 3 s = SLO ceiling
        Cost_norm    = min(cost_usd / max_query_cost_usd, 1.0) — from env config

        Scores can be negative with extreme latency + cost penalties. Minimum
        theoretical value is −0.15 (zero quality, max penalties). Use
        get_deployment_gate() to translate the score into routing decisions.

        Args:
            recall: blended Retrieval sub-score (0.0–1.0) — see
                compute_retrieval_score(), not raw context_recall alone.
            quality: blended Quality sub-score (0.0–1.0) — see
                compute_quality_score(), not raw answer_relevancy alone.
            faithfulness: faithfulness metric (0.0–1.0).
            latency_p95_ms: p95 query latency in milliseconds (non-negative).
            cost_usd: estimated cost per query in USD (non-negative).

        Returns:
            Unified Score (range ≈ −0.15 to 0.85 in practice).

        Raises:
            ValueError: If any metric input is out of valid bounds.
        """
        if not (0.0 <= recall <= 1.0):
            raise ValueError("recall must be between 0.0 and 1.0")
        if not (0.0 <= quality <= 1.0):
            raise ValueError("quality must be between 0.0 and 1.0")
        if not (0.0 <= faithfulness <= 1.0):
            raise ValueError("faithfulness must be between 0.0 and 1.0")
        if latency_p95_ms < 0:
            raise ValueError("latency_p95_ms cannot be negative")
        if cost_usd < 0:
            raise ValueError("cost_usd cannot be negative")

        latency_norm = min(latency_p95_ms / _LATENCY_MAX_MS, 1.0)
        cost_norm = min(cost_usd / max(settings.max_query_cost_usd, 1e-9), 1.0)

        score = round(
            _W_RECALL * recall
            + _W_QUALITY * quality
            + _W_FAITHFULNESS * faithfulness
            - _W_LATENCY * latency_norm
            - _W_COST * cost_norm,
            4,
        )

        logger.info(
            "Unified Score computed",
            extra={
                "score": score,
                "recall": recall,
                "quality": quality,
                "faithfulness": faithfulness,
                "latency_p95_ms": latency_p95_ms,
                "cost_usd": cost_usd,
                "latency_norm": latency_norm,
                "cost_norm": cost_norm,
            },
        )
        return score

    # ─────────────────────────────────────────────────────────────────────────
    # Public: Unified Score provenance (P0.6-3, 13-Jul-2026)
    # ─────────────────────────────────────────────────────────────────────────

    def build_score_provenance(
        self,
        *,
        recall: float,
        quality: float,
        faithfulness: float,
        latency_p95_ms: int | float,
        cost_usd: float,
        unified_score: float,
        evaluation_mode: str,
    ) -> dict[str, Any]:
        """Build the persisted evidence trail for a computed unified_score.

        Every input this method returns is one already used by
        compute_unified_score() for the same call — this does not recompute
        anything from a different source, it just records what went in so a
        historical run's score.py response can explain "why unified_score = X"
        from stored data alone, without depending on transient GraphState
        (P0.6-3 requirement). Stored under
        agent_execution_metadata.score_provenance (JSONB) — no new top-level
        column, same pattern as node_trace/observer_signals (migration 0010).

        Args:
            recall, quality, faithfulness, latency_p95_ms, cost_usd: the exact
                values passed to compute_unified_score() for this run.
            unified_score: the value compute_unified_score() returned.
            evaluation_mode: "FULL" | "DIAGNOSTIC" (ragas_metrics.evaluation_mode).

        Returns:
            Dict with every input, the two computed penalty factors, the
            final score, and the formula version — value_type classification
            (MEASURED/DERIVED/NOT_COLLECTED) is applied by the API layer
            (score.py), not here — this method only records real numbers.
        """
        latency_norm = min(latency_p95_ms / _LATENCY_MAX_MS, 1.0)
        cost_norm = min(cost_usd / max(settings.max_query_cost_usd, 1e-9), 1.0)

        return {
            "recall_input": recall,
            "quality_input": quality,
            "faithfulness_input": faithfulness,
            "latency_p95_ms_input": latency_p95_ms,
            "latency_penalty": round(_W_LATENCY * latency_norm, 4),
            "cost_usd_input": cost_usd,
            "cost_penalty": round(_W_COST * cost_norm, 4),
            "unified_score": unified_score,
            "formula_version": UNIFIED_SCORE_FORMULA_VERSION,
            "evaluation_mode": evaluation_mode,
            "weights": {
                "recall": _W_RECALL,
                "quality": _W_QUALITY,
                "faithfulness": _W_FAITHFULNESS,
                "latency": _W_LATENCY,
                "cost": _W_COST,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Public: Deployment gate routing (D-15 design — clean 4-gate oracle)
    # ─────────────────────────────────────────────────────────────────────────

    def get_deployment_gate(
        self,
        *,
        unified_score: float,
        faithfulness: float,
        adversarial_pass_rate: float,
    ) -> tuple[str, bool]:
        """Determine deployment gate from evaluation results.

        4 gates (CLAUDE.md §9 + evaluator-standards.md §3–5):
            deploy      — score ≥ 0.85, faithfulness ≥ 0.5, adversarial pass
            hitl        — 0.70 ≤ score < 0.85, requires human approval
            retry       — score < 0.70, triggers Diagnoser → Improver loop
            hard_block  — faithfulness < 0.5 OR adversarial_pass_rate < 1.0

        Hard blocks have highest precedence. A score of 0.95 with
        faithfulness 0.42 → hard_block, not deploy. Non-bypassable.

        Args:
            unified_score: Weighted composite score from compute_unified_score().
            faithfulness: RAGAS faithfulness metric (0.0–1.0).
            adversarial_pass_rate: Fraction of adversarial questions passed (0.0–1.0).

        Returns:
            Tuple of (gate_name, approval_required):
              gate_name: "deploy" | "hitl" | "retry" | "hard_block"
              approval_required: True only for the "hitl" gate.
        """
        # Hard blocks take precedence (evaluator-standards.md §6, §7)
        if faithfulness < _FAITHFULNESS_HARD_BLOCK:
            return ("hard_block", False)
        if adversarial_pass_rate < 1.0:
            return ("hard_block", False)

        # Standard routing gates
        if unified_score >= 0.85:
            return ("deploy", False)
        if 0.70 <= unified_score < 0.85:
            return ("hitl", True)
        return ("retry", False)

    # ─────────────────────────────────────────────────────────────────────────
    # Public: MLflow telemetry (Rule 86 §6 — mandatory per evaluation run)
    # ─────────────────────────────────────────────────────────────────────────

    async def log_to_mlflow(
        self,
        *,
        unified_score: float,
        faithfulness: float,
        context_recall: float,
        mrr: float | None,
        ndcg: float | None,
        recall_at_5: float | None,
        recall_at_10: float | None,
        search_latency_ms: float,
        cost_per_query_usd: float,
        latency_p95_ms: float,
        total_tokens: int,
        llm_provider: str,
        evaluation_mode: str = "FULL",
        run_name: str | None = None,
    ) -> None:
        """Open one MLflow run and log up to 11 metrics + 2 params (Rule 86 §6).

        11 metrics (log_metric) when evaluation_mode="FULL":
            unified_score, faithfulness, context_recall, mrr, ndcg,
            recall_at_5, recall_at_10, search_latency_ms,
            cost_per_query_usd, latency_p95_ms, total_tokens

        In DIAGNOSTIC mode (P0.6-1, 13-Jul-2026: no curated ground truth for
        this pipeline/document), mrr/ndcg/recall_at_5/recall_at_10 are None —
        genuinely NOT_COLLECTED, not a fabricated 0.5. mlflow.log_metric()
        rejects None, so those 4 are skipped rather than logged as a fake
        value; the other 7 metrics are always real and always logged.

        2 params (log_param):
            llm_provider, evaluation_mode ("FULL" | "DIAGNOSTIC")

        Args:
            unified_score: Weighted composite gate score.
            faithfulness: RAGAS faithfulness (hard block < 0.5).
            context_recall: RAGAS context recall.
            mrr: Mean Reciprocal Rank, or None if NOT_COLLECTED.
            ndcg: nDCG@10, or None if NOT_COLLECTED.
            recall_at_5: Recall@5, or None if NOT_COLLECTED.
            recall_at_10: Recall@10, or None if NOT_COLLECTED.
            search_latency_ms: Retrieval latency in ms.
            cost_per_query_usd: Estimated USD cost per query.
            latency_p95_ms: p95 end-to-end query latency in ms.
            total_tokens: Total tokens consumed in this evaluation run.
            llm_provider: Provider used (gemini-flash-3.5 | kimi-k2.6 | gemini-3.5).
            evaluation_mode: "FULL" (ground truth available) or "DIAGNOSTIC".
            run_name: Optional MLflow run name for human readability.
        """
        try:
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment(settings.mlflow_experiment_name)

            with mlflow.start_run(run_name=run_name):
                # Always-real metrics — Rule 86 §6
                mlflow.log_metric("unified_score", unified_score)
                mlflow.log_metric("faithfulness", faithfulness)
                mlflow.log_metric("context_recall", context_recall)
                mlflow.log_metric("search_latency_ms", search_latency_ms)
                mlflow.log_metric("cost_per_query_usd", cost_per_query_usd)
                mlflow.log_metric("latency_p95_ms", latency_p95_ms)
                mlflow.log_metric("total_tokens", float(total_tokens))

                # Ground-truth-dependent ranking metrics — only when measured
                for name, value in (
                    ("mrr", mrr),
                    ("ndcg", ndcg),
                    ("recall_at_5", recall_at_5),
                    ("recall_at_10", recall_at_10),
                ):
                    if value is not None:
                        mlflow.log_metric(name, value)

                # Params — Rule 86 §6 + P0.6-1 provenance
                mlflow.log_param("llm_provider", llm_provider)
                mlflow.log_param("evaluation_mode", evaluation_mode)

            logger.info(
                "MLflow evaluation run logged",
                extra={
                    "experiment": settings.mlflow_experiment_name,
                    "unified_score": unified_score,
                    "llm_provider": llm_provider,
                },
            )
        except Exception as exc:
            # MLflow failure must not block deployment decision — log and continue.
            # The evaluation result is the source of truth, not the telemetry.
            logger.error(
                "MLflow logging failed — evaluation result unaffected",
                extra={"error": str(exc)},
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Public: Stubs implemented (previously raised NotImplementedError)
    # ─────────────────────────────────────────────────────────────────────────

    async def start_evaluation(self, pipeline_id: str, trace_id: str) -> str:
        """Enqueue a LangGraph evaluation job via Redis and return job_id.

        Implementation: Owned by the /api/v1/evaluate route + Redis queue worker.
        This stub returns a placeholder until the Redis worker integration (E-3)
        is wired. The evaluator LangGraph node does the actual computation.
        """
        raise EvaluationFailedError(
            "start_evaluation: Redis job queue not yet wired (see E-3). "
            "Call evaluator_node directly via LangGraph graph execution."
        )

    async def get_results(self, run_id: str, organization_id: str) -> dict:
        """Fetch completed evaluation results from EvaluationRepository.

        Implementation: Owned by the /api/v1/score/{run_id} route handler.
        Wired to EvaluationRepository in the routes layer.
        """
        raise EvaluationFailedError(
            "get_results: Implement in /api/v1/score route handler via EvaluationRepository."
        )
