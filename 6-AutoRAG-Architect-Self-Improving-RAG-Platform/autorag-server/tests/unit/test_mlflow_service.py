"""Unit tests for MLflowService.

Task E-3: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Rule 86: every evaluation run must log 5 mandatory metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.mlflow_service import (
    EvalRunMetrics,
    MLflowRunResult,
    MLflowService,
    PipelineRunParams,
)


@pytest.fixture
def svc() -> MLflowService:
    return MLflowService()


@pytest.fixture
def metrics() -> EvalRunMetrics:
    return EvalRunMetrics(
        unified_score=0.89,
        cost_per_query_usd=0.006,
        latency_p95_ms=1200.0,
        total_tokens=540,
        llm_provider_used="gemini-flash-3.5",
        faithfulness=0.85,
        score_delta=0.04,
        failure_type="F-01",
    )


@pytest.fixture
def params() -> PipelineRunParams:
    return PipelineRunParams(
        chunk_strategy="hierarchical",
        chunk_size=512,
        k_value=10,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


def test_log_eval_run_returns_success(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """Successful MLflow run returns success=True with a run_id."""
    fake_run = MagicMock()
    fake_run.info.run_id = "fake-run-id-001"

    with (
        patch.object(svc, "_setup_tracking"),
        patch("app.services.mlflow_service.mlflow.set_experiment"),
        patch("app.services.mlflow_service.mlflow.start_run") as mock_run,
        patch("app.services.mlflow_service.mlflow.log_metrics"),
        patch("app.services.mlflow_service.mlflow.log_param"),
        patch("app.services.mlflow_service.mlflow.log_params"),
        patch("app.services.mlflow_service.mlflow.set_tags"),
    ):
        mock_run.return_value.__enter__ = MagicMock(return_value=fake_run)
        mock_run.return_value.__exit__ = MagicMock(return_value=False)

        result = svc.log_eval_run(
            pipeline_id="pipe-001",
            variant_id="var-001",
            metrics=metrics,
            params=params,
            x_trace_id="trace-abc",
        )

    assert isinstance(result, MLflowRunResult)
    assert result.success is True


def test_log_eval_run_sets_correct_experiment_name(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """Experiment name must be autorag-pipeline-{pipeline_id}."""
    fake_run = MagicMock()
    fake_run.info.run_id = "fake-run-id-002"

    with (
        patch.object(svc, "_setup_tracking"),
        patch("app.services.mlflow_service.mlflow.set_experiment") as mock_exp,
        patch("app.services.mlflow_service.mlflow.start_run") as mock_run,
        patch("app.services.mlflow_service.mlflow.log_metrics"),
        patch("app.services.mlflow_service.mlflow.log_param"),
        patch("app.services.mlflow_service.mlflow.log_params"),
        patch("app.services.mlflow_service.mlflow.set_tags"),
    ):
        mock_run.return_value.__enter__ = MagicMock(return_value=fake_run)
        mock_run.return_value.__exit__ = MagicMock(return_value=False)

        svc.log_eval_run(
            pipeline_id="pipe-xyz",
            variant_id="var-001",
            metrics=metrics,
            params=params,
            x_trace_id="trace-abc",
        )

    mock_exp.assert_called_once_with("autorag-pipeline-pipe-xyz")


def test_log_eval_run_logs_4_numeric_metrics(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """Rule 86: 4 mandatory numeric metrics must be logged."""
    fake_run = MagicMock()
    fake_run.info.run_id = "fake-run-id-003"
    logged_metrics: dict[str, float] = {}

    def capture_metrics(m: dict[str, float]) -> None:
        logged_metrics.update(m)

    with (
        patch.object(svc, "_setup_tracking"),
        patch("app.services.mlflow_service.mlflow.set_experiment"),
        patch("app.services.mlflow_service.mlflow.start_run") as mock_run,
        patch("app.services.mlflow_service.mlflow.log_metrics", side_effect=capture_metrics),
        patch("app.services.mlflow_service.mlflow.log_param"),
        patch("app.services.mlflow_service.mlflow.log_params"),
        patch("app.services.mlflow_service.mlflow.set_tags"),
    ):
        mock_run.return_value.__enter__ = MagicMock(return_value=fake_run)
        mock_run.return_value.__exit__ = MagicMock(return_value=False)

        svc.log_eval_run(
            pipeline_id="pipe-001",
            variant_id="var-001",
            metrics=metrics,
            params=params,
            x_trace_id="trace-abc",
        )

    assert "unified_score" in logged_metrics
    assert "cost_per_query_usd" in logged_metrics
    assert "latency_p95_ms" in logged_metrics
    assert "total_tokens" in logged_metrics


def test_log_eval_run_logs_llm_provider_as_param(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """Rule 86: llm_provider_used must be logged as param (string), not metric."""
    fake_run = MagicMock()
    fake_run.info.run_id = "fake-run-id-004"
    logged_params: list[tuple[str, object]] = []

    def capture_param(k: str, v: object) -> None:
        logged_params.append((k, v))

    with (
        patch.object(svc, "_setup_tracking"),
        patch("app.services.mlflow_service.mlflow.set_experiment"),
        patch("app.services.mlflow_service.mlflow.start_run") as mock_run,
        patch("app.services.mlflow_service.mlflow.log_metrics"),
        patch("app.services.mlflow_service.mlflow.log_param", side_effect=capture_param),
        patch("app.services.mlflow_service.mlflow.log_params"),
        patch("app.services.mlflow_service.mlflow.set_tags"),
    ):
        mock_run.return_value.__enter__ = MagicMock(return_value=fake_run)
        mock_run.return_value.__exit__ = MagicMock(return_value=False)

        svc.log_eval_run(
            pipeline_id="pipe-001",
            variant_id="var-001",
            metrics=metrics,
            params=params,
            x_trace_id="trace-abc",
        )

    param_keys = [k for k, _ in logged_params]
    assert "llm_provider_used" in param_keys


def test_log_eval_run_tags_include_x_trace_id(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """x_trace_id must appear in MLflow tags for distributed tracing."""
    fake_run = MagicMock()
    fake_run.info.run_id = "fake-run-id-005"
    logged_tags: dict[str, str] = {}

    with (
        patch.object(svc, "_setup_tracking"),
        patch("app.services.mlflow_service.mlflow.set_experiment"),
        patch("app.services.mlflow_service.mlflow.start_run") as mock_run,
        patch("app.services.mlflow_service.mlflow.log_metrics"),
        patch("app.services.mlflow_service.mlflow.log_param"),
        patch("app.services.mlflow_service.mlflow.log_params"),
        patch("app.services.mlflow_service.mlflow.set_tags", side_effect=logged_tags.update),
    ):
        mock_run.return_value.__enter__ = MagicMock(return_value=fake_run)
        mock_run.return_value.__exit__ = MagicMock(return_value=False)

        svc.log_eval_run(
            pipeline_id="pipe-001",
            variant_id="var-001",
            metrics=metrics,
            params=params,
            x_trace_id="trace-xyz",
        )

    assert logged_tags.get("x_trace_id") == "trace-xyz"


# ─────────────────────────────────────────────────────────────────────────────
# Failure resilience — must NOT block pipeline
# ─────────────────────────────────────────────────────────────────────────────


def test_log_eval_run_returns_failure_on_mlflow_error(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """MLflow failure must return success=False — not raise (Rule 86 resilience)."""
    with (
        patch.object(svc, "_setup_tracking"),
        patch("app.services.mlflow_service.mlflow.set_experiment", side_effect=Exception("mlflow down")),
    ):
        result = svc.log_eval_run(
            pipeline_id="pipe-001",
            variant_id="var-001",
            metrics=metrics,
            params=params,
            x_trace_id="trace-abc",
        )

    assert result.success is False
    assert result.run_id == ""


def test_log_eval_run_does_not_raise_on_failure(
    svc: MLflowService,
    metrics: EvalRunMetrics,
    params: PipelineRunParams,
) -> None:
    """MLflow errors must be swallowed — caller pipeline must not crash."""
    with patch.object(svc, "_setup_tracking", side_effect=Exception("conn refused")):
        try:
            svc.log_eval_run(
                pipeline_id="pipe-001",
                variant_id="var-001",
                metrics=metrics,
                params=params,
                x_trace_id="trace-abc",
            )
        except Exception:  # noqa: BLE001
            pytest.fail("MLflowService.log_eval_run raised — must not raise on failure")


# ─────────────────────────────────────────────────────────────────────────────
# Improver wiring — E-16: CostGuardrail + TokenGuardrail called in improver
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_improver_calls_cost_guardrail() -> None:
    """E-16: CostGuardrail.check() must be called before variant generation."""
    from app.core.state import GraphState
    from app.graph.nodes.improver import improver_node
    from app.services.cost_guardrail import CostCheckResult

    state = GraphState(
        state_version="v1",
        run_id="run-001",
        pipeline_id="pipe-001",
        organization_id="org-001",
        x_trace_id="trace-e16",
        failure_type="F-01",
        unified_score=0.65,
        execution_trace=[],
        guardrail_blocked=False,
        guardrail_block_reason=None,
    )

    allowed_result = CostCheckResult(
        allowed=True,
        budget_type=__import__("app.services.cost_guardrail", fromlist=["CostBudgetType"]).CostBudgetType.PIPELINE_BUILD,
        estimated_cost_usd=0.009,
        budget_limit_usd=5.0,
        reason="within budget",
    )

    with (
        patch("app.graph.nodes.improver._cost_guardrail.check", return_value=allowed_result) as mock_cost,
        patch("app.graph.nodes.improver._token_guardrail.check") as mock_token,
        patch("app.graph.nodes.improver._log_to_mlflow", return_value="mlflow-run-id"),
    ):
        mock_token.return_value = __import__(
            "app.services.token_guardrail", fromlist=["TokenCheckResult"]
        ).TokenCheckResult(
            allowed=True,
            budget_type=__import__("app.services.token_guardrail", fromlist=["TokenBudgetType"]).TokenBudgetType.PROMPT,
            requested_tokens=5120,
            budget_limit=32000,
            reason="within token budget",
        )
        await improver_node(state)

    mock_cost.assert_called_once()


@pytest.mark.asyncio
async def test_improver_calls_token_guardrail() -> None:
    """E-17: TokenGuardrail.check() must be called before context expansion."""
    from app.core.state import GraphState
    from app.graph.nodes.improver import improver_node
    from app.services.cost_guardrail import CostBudgetType, CostCheckResult
    from app.services.token_guardrail import TokenBudgetType, TokenCheckResult

    state = GraphState(
        state_version="v1",
        run_id="run-002",
        pipeline_id="pipe-002",
        organization_id="org-001",
        x_trace_id="trace-e17",
        failure_type="F-04",
        unified_score=0.60,
        execution_trace=[],
        guardrail_blocked=False,
        guardrail_block_reason=None,
    )

    with (
        patch("app.graph.nodes.improver._token_guardrail.check") as mock_token,
        patch("app.graph.nodes.improver._cost_guardrail.check") as mock_cost,
        patch("app.graph.nodes.improver._log_to_mlflow", return_value="mlflow-run-id"),
    ):
        mock_token.return_value = TokenCheckResult(
            allowed=True,
            budget_type=TokenBudgetType.PROMPT,
            requested_tokens=5120,
            budget_limit=32000,
            reason="within token budget",
        )
        mock_cost.return_value = CostCheckResult(
            allowed=True,
            budget_type=CostBudgetType.PIPELINE_BUILD,
            estimated_cost_usd=0.009,
            budget_limit_usd=5.0,
            reason="within budget",
        )
        await improver_node(state)

    mock_token.assert_called_once()
