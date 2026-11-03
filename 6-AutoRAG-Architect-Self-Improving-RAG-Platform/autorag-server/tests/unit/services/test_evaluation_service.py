"""Unit tests for EvaluationService — D-15 Unified Score Formula (merged into D-16).

Test coverage:
  - Formula computation (frozen weights: 0.25R + 0.35Q + 0.25F - 0.10L - 0.05C)
  - Deployment gate logic (deploy/hitl/retry/hard_block) — D-15 get_deployment_gate()
  - Input validation (bounds checking 0.0 - 1.0, negative latency/cost)
  - Latency/cost normalization (raw → 0.0-1.0 scale, cap at 1.0)
  - MLflow telemetry (Rule 86 §6 — 11 metrics + 1 param, graceful degradation)

All tests are pure unit tests — no database or LLM calls required.
Real wiring tests belong in tests/integration/test_ragas_service.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.evaluation_service import EvaluationService

# ══════════════════════════════════════════════════════════════════════════════
# Test Class 1: compute_unified_score() — Formula Logic
# ══════════════════════════════════════════════════════════════════════════════


class TestComputeUnifiedScore:
    """Tests for the frozen formula implementation."""

    @pytest.fixture
    def service(self) -> EvaluationService:
        return EvaluationService()

    def test_compute_valid_inputs_high_quality(self, service: EvaluationService) -> None:
        """Happy path — realistic high-quality pipeline."""
        score = service.compute_unified_score(
            recall=0.90,
            quality=0.88,
            faithfulness=0.85,
            latency_p95_ms=1200,  # normalizes to 0.4 (1200/3000)
            cost_usd=0.003,       # normalizes to 0.3 (0.003/0.01)
        )
        # Expected: (0.25×0.90) + (0.35×0.88) + (0.25×0.85) − (0.10×0.4) − (0.05×0.3)
        #         = 0.225 + 0.308 + 0.2125 − 0.04 − 0.015 = 0.6905
        assert 0.68 < score < 0.71, f"Expected ~0.69, got {score}"

    def test_compute_perfect_inputs(self, service: EvaluationService) -> None:
        """Edge case — all metrics perfect, zero latency/cost."""
        score = service.compute_unified_score(
            recall=1.0,
            quality=1.0,
            faithfulness=1.0,
            latency_p95_ms=0,
            cost_usd=0.0,
        )
        # Expected: (0.25×1.0) + (0.35×1.0) + (0.25×1.0) − 0 − 0 = 0.85
        assert score == pytest.approx(0.85, abs=0.01)

    def test_compute_with_high_latency_penalty(self, service: EvaluationService) -> None:
        """Latency above threshold (3000ms) is capped — max penalty applied."""
        score = service.compute_unified_score(
            recall=0.95,
            quality=0.90,
            faithfulness=0.88,
            latency_p95_ms=5000,  # exceeds 3000ms baseline → capped at 1.0
            cost_usd=0.002,
        )
        # Latency normalized: min(5000/3000, 1.0) = 1.0 → penalty -0.10
        # Base: (0.25×0.95) + (0.35×0.90) + (0.25×0.88) = 0.7725
        # Cost penalty: -0.05×(0.002/0.01) = -0.01
        # Total: 0.7725 − 0.10 − 0.01 = 0.6625
        assert 0.65 < score < 0.68, f"Expected ~0.66, got {score}"

    def test_compute_with_high_cost_penalty(self, service: EvaluationService) -> None:
        """Cost above threshold ($0.01 USD) is capped — max penalty applied."""
        score = service.compute_unified_score(
            recall=0.92,
            quality=0.89,
            faithfulness=0.90,
            latency_p95_ms=1500,
            cost_usd=0.015,  # exceeds $0.01 baseline → capped at 1.0
        )
        # Cost normalized: min(0.015/0.01, 1.0) = 1.0 → penalty -0.05
        # Latency normalized: 1500/3000 = 0.5 → penalty -0.05
        # Base: (0.25×0.92) + (0.35×0.89) + (0.25×0.90) = 0.7675
        # Total: 0.7675 − 0.05 − 0.05 = 0.6675
        assert 0.65 < score < 0.69, f"Expected ~0.67, got {score}"

    def test_compute_rejects_negative_recall(self, service: EvaluationService) -> None:
        """Input validation — recall must be 0.0 - 1.0."""
        with pytest.raises(ValueError, match="recall must be between 0.0 and 1.0"):
            service.compute_unified_score(
                recall=-0.1, quality=0.8, faithfulness=0.7,
                latency_p95_ms=2000, cost_usd=0.005,
            )

    def test_compute_rejects_recall_above_1(self, service: EvaluationService) -> None:
        """Input validation — recall cannot exceed 1.0."""
        with pytest.raises(ValueError, match="recall must be between 0.0 and 1.0"):
            service.compute_unified_score(
                recall=1.5, quality=0.9, faithfulness=0.8,
                latency_p95_ms=1800, cost_usd=0.006,
            )

    def test_compute_rejects_negative_latency(self, service: EvaluationService) -> None:
        """Input validation — latency_p95_ms cannot be negative."""
        with pytest.raises(ValueError, match="latency_p95_ms cannot be negative"):
            service.compute_unified_score(
                recall=0.88, quality=0.85, faithfulness=0.80,
                latency_p95_ms=-100, cost_usd=0.004,
            )

    def test_compute_rejects_negative_cost(self, service: EvaluationService) -> None:
        """Input validation — cost_usd cannot be negative."""
        with pytest.raises(ValueError, match="cost_usd cannot be negative"):
            service.compute_unified_score(
                recall=0.90, quality=0.87, faithfulness=0.82,
                latency_p95_ms=2200, cost_usd=-0.001,
            )

    def test_score_can_go_negative_with_extreme_penalties(
        self, service: EvaluationService
    ) -> None:
        """Score is not clamped — extreme penalties can produce negative values."""
        score = service.compute_unified_score(
            recall=0.0, quality=0.0, faithfulness=0.0,
            latency_p95_ms=100_000, cost_usd=100.0,
        )
        # 0 positive weight + max penalties (-0.10 − 0.05) = -0.15
        assert score < 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 1b: compute_retrieval_score() — v1.2 Retrieval sub-formula
# ══════════════════════════════════════════════════════════════════════════════


class TestComputeRetrievalScore:
    """Tests for Retrieval = 0.5*ContextPrecision + 0.5*ContextRecall."""

    @pytest.fixture
    def service(self) -> EvaluationService:
        return EvaluationService()

    def test_equal_weight_blend(self, service: EvaluationService) -> None:
        score = service.compute_retrieval_score(context_precision=0.8, context_recall=0.6)
        assert score == pytest.approx(0.7, abs=0.0001)

    def test_perfect_inputs(self, service: EvaluationService) -> None:
        score = service.compute_retrieval_score(context_precision=1.0, context_recall=1.0)
        assert score == pytest.approx(1.0, abs=0.0001)

    def test_zero_inputs(self, service: EvaluationService) -> None:
        score = service.compute_retrieval_score(context_precision=0.0, context_recall=0.0)
        assert score == pytest.approx(0.0, abs=0.0001)

    def test_asymmetric_inputs_averaged_equally(self, service: EvaluationService) -> None:
        """High precision, low recall (or vice versa) should land at the midpoint —
        no single metric dominates the blend."""
        score_a = service.compute_retrieval_score(context_precision=1.0, context_recall=0.0)
        score_b = service.compute_retrieval_score(context_precision=0.0, context_recall=1.0)
        assert score_a == pytest.approx(0.5, abs=0.0001)
        assert score_a == score_b

    def test_rejects_out_of_bounds_precision(self, service: EvaluationService) -> None:
        with pytest.raises(ValueError, match="context_precision"):
            service.compute_retrieval_score(context_precision=1.1, context_recall=0.5)

    def test_rejects_out_of_bounds_recall(self, service: EvaluationService) -> None:
        with pytest.raises(ValueError, match="context_recall"):
            service.compute_retrieval_score(context_precision=0.5, context_recall=-0.1)


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 1c: compute_quality_score() — v1.2 Quality sub-formula
# ══════════════════════════════════════════════════════════════════════════════


class TestComputeQualityScore:
    """Tests for Quality = 0.6*AnswerCorrectness + 0.4*AnswerRelevancy,
    with the answer_correctness=None -> answer_relevancy-only fallback."""

    @pytest.fixture
    def service(self) -> EvaluationService:
        return EvaluationService()

    def test_blend_with_ground_truth(self, service: EvaluationService) -> None:
        score = service.compute_quality_score(answer_relevancy=0.8, answer_correctness=0.9)
        # 0.6*0.9 + 0.4*0.8 = 0.54 + 0.32 = 0.86
        assert score == pytest.approx(0.86, abs=0.0001)

    def test_no_ground_truth_falls_back_to_relevancy_alone(
        self, service: EvaluationService
    ) -> None:
        """answer_correctness=None (the common case, no golden-dataset ground
        truth seeded) must fall back to answer_relevancy alone -- not 0, not a
        fabricated value."""
        score = service.compute_quality_score(answer_relevancy=0.75, answer_correctness=None)
        assert score == pytest.approx(0.75, abs=0.0001)

    def test_perfect_inputs(self, service: EvaluationService) -> None:
        score = service.compute_quality_score(answer_relevancy=1.0, answer_correctness=1.0)
        assert score == pytest.approx(1.0, abs=0.0001)

    def test_correctness_weighted_higher_than_relevancy(
        self, service: EvaluationService
    ) -> None:
        """A perfect correctness + zero relevancy should score higher than the
        reverse -- confirms the 0.6/0.4 weighting, not an accidental 0.5/0.5."""
        high_correctness = service.compute_quality_score(
            answer_relevancy=0.0, answer_correctness=1.0
        )
        high_relevancy = service.compute_quality_score(
            answer_relevancy=1.0, answer_correctness=0.0
        )
        assert high_correctness > high_relevancy
        assert high_correctness == pytest.approx(0.6, abs=0.0001)
        assert high_relevancy == pytest.approx(0.4, abs=0.0001)

    def test_rejects_out_of_bounds_relevancy(self, service: EvaluationService) -> None:
        with pytest.raises(ValueError, match="answer_relevancy"):
            service.compute_quality_score(answer_relevancy=1.5, answer_correctness=0.5)

    def test_rejects_out_of_bounds_correctness(self, service: EvaluationService) -> None:
        with pytest.raises(ValueError, match="answer_correctness"):
            service.compute_quality_score(answer_relevancy=0.5, answer_correctness=-0.5)


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 2: get_deployment_gate() — 4-Gate Routing Logic
# ══════════════════════════════════════════════════════════════════════════════


class TestDeploymentGate:
    """Tests for the 4-gate routing decision (deploy/hitl/retry/hard_block)."""

    @pytest.fixture
    def service(self) -> EvaluationService:
        return EvaluationService()

    def test_gate_deploy_when_score_above_085(self, service: EvaluationService) -> None:
        """Gate: deploy — score ≥ 0.85, faithfulness ≥ 0.5, adversarial pass."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.90,
            faithfulness=0.78,
            adversarial_pass_rate=1.0,
        )
        assert gate == "deploy"
        assert approval_required is False

    def test_gate_hitl_when_score_between_070_and_085(
        self, service: EvaluationService
    ) -> None:
        """Gate: hitl — 0.70 ≤ score < 0.85, requires human approval."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.78,
            faithfulness=0.65,
            adversarial_pass_rate=1.0,
        )
        assert gate == "hitl"
        assert approval_required is True

    def test_gate_retry_when_score_below_070(self, service: EvaluationService) -> None:
        """Gate: retry — score < 0.70, triggers Diagnoser → Improver loop."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.62,
            faithfulness=0.58,
            adversarial_pass_rate=1.0,
        )
        assert gate == "retry"
        assert approval_required is False

    def test_gate_hard_block_when_faithfulness_below_05(
        self, service: EvaluationService
    ) -> None:
        """Gate: hard_block — faithfulness < 0.5 is non-bypassable."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.92,  # high score doesn't override
            faithfulness=0.42,
            adversarial_pass_rate=1.0,
        )
        assert gate == "hard_block"
        assert approval_required is False

    def test_gate_hard_block_when_adversarial_fails(
        self, service: EvaluationService
    ) -> None:
        """Gate: hard_block — adversarial_pass_rate < 1.0 blocks deployment."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.88,
            faithfulness=0.75,
            adversarial_pass_rate=0.9,  # 9/10 — not enough
        )
        assert gate == "hard_block"
        assert approval_required is False

    def test_gate_faithfulness_hard_block_overrides_deploy(
        self, service: EvaluationService
    ) -> None:
        """Hard block takes precedence over deploy gate."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.95,   # would qualify for deploy
            faithfulness=0.48,    # but faithfulness fails → hard block wins
            adversarial_pass_rate=1.0,
        )
        assert gate == "hard_block"
        assert approval_required is False

    def test_gate_edge_case_score_exactly_085(self, service: EvaluationService) -> None:
        """Edge case — score = 0.85 exactly qualifies for deploy."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.85,
            faithfulness=0.50,  # exactly at threshold
            adversarial_pass_rate=1.0,
        )
        assert gate == "deploy"
        assert approval_required is False

    def test_gate_edge_case_score_exactly_070(self, service: EvaluationService) -> None:
        """Edge case — score = 0.70 exactly qualifies for hitl."""
        gate, approval_required = service.get_deployment_gate(
            unified_score=0.70,
            faithfulness=0.60,
            adversarial_pass_rate=1.0,
        )
        assert gate == "hitl"
        assert approval_required is True


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 3: Normalization Logic — Latency & Cost
# ══════════════════════════════════════════════════════════════════════════════


class TestNormalization:
    """Tests for latency and cost normalization to 0.0-1.0 scale."""

    @pytest.fixture
    def service(self) -> EvaluationService:
        return EvaluationService()

    def test_latency_zero_yields_zero_penalty(self, service: EvaluationService) -> None:
        """Latency = 0ms → normalized = 0.0 → no penalty."""
        score = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=0, cost_usd=0.0,
        )
        # Base: (0.25×0.80) + (0.35×0.80) + (0.25×0.80) = 0.68
        assert score == pytest.approx(0.68, abs=0.01)

    def test_latency_at_threshold_3000ms(self, service: EvaluationService) -> None:
        """Latency = 3000ms → normalized = 1.0 → full penalty -0.10."""
        score = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=3000, cost_usd=0.0,
        )
        # Base: 0.68, Latency penalty: -0.10×1.0 = -0.10
        # Total: 0.68 - 0.10 = 0.58
        assert score == pytest.approx(0.58, abs=0.01)

    def test_cost_at_threshold_001_usd(self, service: EvaluationService) -> None:
        """Cost = $0.01 → normalized = 1.0 → full penalty -0.05."""
        score = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=0, cost_usd=0.01,
        )
        # Base: 0.68, Cost penalty: -0.05×1.0 = -0.05
        # Total: 0.68 - 0.05 = 0.63
        assert score == pytest.approx(0.63, abs=0.01)

    def test_latency_above_threshold_capped_at_1(self, service: EvaluationService) -> None:
        """Latency > 3000ms is capped at normalized 1.0 (max penalty = -0.10)."""
        score_5000ms = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=5000, cost_usd=0.0,
        )
        score_10000ms = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=10000, cost_usd=0.0,
        )
        # Both: 0.68 - 0.10 = 0.58
        assert score_5000ms == pytest.approx(0.58, abs=0.01)
        assert score_10000ms == pytest.approx(0.58, abs=0.01)

    def test_cost_above_threshold_capped_at_1(self, service: EvaluationService) -> None:
        """Cost > $0.01 is capped at normalized 1.0 (max penalty = -0.05)."""
        score_002_usd = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=0, cost_usd=0.02,
        )
        score_005_usd = service.compute_unified_score(
            recall=0.80, quality=0.80, faithfulness=0.80,
            latency_p95_ms=0, cost_usd=0.05,
        )
        # Both: 0.68 - 0.05 = 0.63
        assert score_002_usd == pytest.approx(0.63, abs=0.01)
        assert score_005_usd == pytest.approx(0.63, abs=0.01)


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 4: log_to_mlflow() — Rule 86 §6 MLflow Telemetry
# ══════════════════════════════════════════════════════════════════════════════

_MLFLOW_MODULE = "app.services.evaluation_service.mlflow"

_SAMPLE_KWARGS: dict[str, object] = {
    "unified_score": 0.87,
    "faithfulness": 0.80,
    "context_recall": 0.85,
    "mrr": 0.90,
    "ndcg": 0.88,
    "recall_at_5": 0.92,
    "recall_at_10": 0.95,
    "search_latency_ms": 450.0,
    "cost_per_query_usd": 0.003,
    "latency_p95_ms": 1500.0,
    "total_tokens": 512,
    "llm_provider": "gemini-flash-3.5",
}

_MANDATORY_METRICS = {
    "unified_score",
    "faithfulness",
    "context_recall",
    "mrr",
    "ndcg",
    "recall_at_5",
    "recall_at_10",
    "search_latency_ms",
    "cost_per_query_usd",
    "latency_p95_ms",
    "total_tokens",
}


class TestMLflowTelemetry:
    """Tests for log_to_mlflow() — Rule 86 §6 compliance.

    Patches `mlflow` at the evaluation_service module level so no real
    MLflow server is needed. Tests verify the exact 11 metrics + 1 param
    contract defined in Rule 86 §6.
    """

    @pytest.fixture
    def service(self) -> EvaluationService:
        return EvaluationService()

    @pytest.mark.asyncio
    async def test_logs_all_11_mandatory_metrics(
        self, service: EvaluationService
    ) -> None:
        """Rule 86 §6: exactly 11 log_metric() calls, one per mandatory key."""
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

            await service.log_to_mlflow(**_SAMPLE_KWARGS)

        logged_keys = {
            c.args[0] for c in mock_mlflow.log_metric.call_args_list
        }
        assert logged_keys == _MANDATORY_METRICS, (
            f"Missing metrics: {_MANDATORY_METRICS - logged_keys}\n"
            f"Extra metrics: {logged_keys - _MANDATORY_METRICS}"
        )

    @pytest.mark.asyncio
    async def test_logs_llm_provider_and_evaluation_mode_params(
        self, service: EvaluationService
    ) -> None:
        """Rule 86 §6 + P0.6-1 (13-Jul-2026): 2 log_param() calls —
        llm_provider (Rule 86) and evaluation_mode (P0.6-1 provenance;
        defaults to "FULL" when the caller doesn't pass it explicitly)."""
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

            await service.log_to_mlflow(**_SAMPLE_KWARGS)

        assert mock_mlflow.log_param.call_count == 2
        logged_params = dict(c.args for c in mock_mlflow.log_param.call_args_list)
        assert logged_params == {"llm_provider": "gemini-flash-3.5", "evaluation_mode": "FULL"}

    @pytest.mark.asyncio
    async def test_metric_values_match_inputs(
        self, service: EvaluationService
    ) -> None:
        """Metric values logged must match the inputs — no silent rounding."""
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

            await service.log_to_mlflow(**_SAMPLE_KWARGS)

        logged = {c.args[0]: c.args[1] for c in mock_mlflow.log_metric.call_args_list}
        assert logged["unified_score"] == pytest.approx(0.87)
        assert logged["faithfulness"] == pytest.approx(0.80)
        assert logged["total_tokens"] == pytest.approx(512.0)
        assert logged["cost_per_query_usd"] == pytest.approx(0.003)

    @pytest.mark.asyncio
    async def test_mlflow_failure_does_not_raise(
        self, service: EvaluationService
    ) -> None:
        """MLflow outage must not block the evaluation result (graceful degradation)."""
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.set_tracking_uri.side_effect = ConnectionError("MLflow unreachable")

            # Must complete without raising — failure is logged and swallowed
            await service.log_to_mlflow(**_SAMPLE_KWARGS)

    @pytest.mark.asyncio
    async def test_run_name_passed_to_start_run(
        self, service: EvaluationService
    ) -> None:
        """Optional run_name is forwarded to mlflow.start_run()."""
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

            await service.log_to_mlflow(**_SAMPLE_KWARGS, run_name="pipeline-v2-eval")

        mock_mlflow.start_run.assert_called_once_with(run_name="pipeline-v2-eval")

    @pytest.mark.asyncio
    async def test_log_metric_count_is_exactly_11(
        self, service: EvaluationService
    ) -> None:
        """Guard against accidental metric additions or omissions."""
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

            await service.log_to_mlflow(**_SAMPLE_KWARGS)

        assert mock_mlflow.log_metric.call_count == 11, (
            f"Expected exactly 11 log_metric calls, got {mock_mlflow.log_metric.call_count}"
        )

    @pytest.mark.asyncio
    async def test_diagnostic_mode_skips_none_ranking_metrics(
        self, service: EvaluationService
    ) -> None:
        """P0.6-1 (13-Jul-2026): mrr/ndcg/recall_at_5/recall_at_10 are None in
        DIAGNOSTIC mode (no ground truth) -- must be skipped, never logged as
        a fabricated number. The other 7 always-real metrics still log."""
        diagnostic_kwargs = {
            **_SAMPLE_KWARGS,
            "mrr": None,
            "ndcg": None,
            "recall_at_5": None,
            "recall_at_10": None,
            "evaluation_mode": "DIAGNOSTIC",
        }
        with patch(_MLFLOW_MODULE) as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
            mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

            await service.log_to_mlflow(**diagnostic_kwargs)

        logged_keys = {c.args[0] for c in mock_mlflow.log_metric.call_args_list}
        assert logged_keys == {
            "unified_score",
            "faithfulness",
            "context_recall",
            "search_latency_ms",
            "cost_per_query_usd",
            "latency_p95_ms",
            "total_tokens",
        }
        logged_params = dict(c.args for c in mock_mlflow.log_param.call_args_list)
        assert logged_params["evaluation_mode"] == "DIAGNOSTIC"
