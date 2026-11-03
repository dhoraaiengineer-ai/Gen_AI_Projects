"""Unit tests for Agent 6 — Observer node.

Task F-9: Ashish Singh (Team 1)
Rule 80: 90% coverage of all critical node paths.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.state import GraphState
from app.graph.nodes.observer import observer_node


@pytest.fixture
def base_state() -> GraphState:
    return GraphState(
        graph_state_version="v1.0",
        run_id="3d8e5792-7f9e-4e4b-8e2b-7c6d5e4f3a2b",  # Must be a valid UUID string
        pipeline_id="7f0b9f91-2dc0-466d-ad50-c8f93666b6c0",
        organization_id="1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
        x_trace_id="trace-xyz",
        llm_provider_used="gemini-flash-3.5",
        unified_score=0.82,
        latency_p95_ms=1200,
        cost_per_query_usd=0.002,
        retry_count=0,
        execution_trace=[],
    )


@pytest.fixture
def mock_run_completed() -> MagicMock:
    run = MagicMock()
    run.run_id = uuid.uuid4()
    run.unified_score = 0.82
    run.status = "completed"
    return run


@pytest.fixture
def mock_run_failed() -> MagicMock:
    run = MagicMock()
    run.run_id = uuid.uuid4()
    run.unified_score = 0.0
    run.status = "failed"
    return run


@pytest.fixture
def mock_db() -> MagicMock:
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = MagicMock()  # synchronous in ORM, but refresh can be mocked

    mock_engine_context = MagicMock()
    mock_engine_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_engine_context.__aexit__ = AsyncMock()

    # Returning the session maker mockup
    session_maker = MagicMock(return_value=mock_engine_context)
    return session_maker


# ─────────────────────────────────────────────────────────────────────────────
# Happy path test
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_observer_happy_path(
    base_state: GraphState, mock_run_completed: MagicMock, mock_db: MagicMock
) -> None:
    """If metrics are within thresholds and stable, alerts must be False and trend stable."""
    with (
        patch("app.graph.nodes.observer.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.observer.EvaluationRepository.list_by_pipeline",
            new_callable=AsyncMock,
        ) as mock_list,
        patch("app.metrics.AGENT_COST.labels") as mock_agent_cost,
        patch("app.metrics.AGENT_LATENCY.labels") as mock_agent_latency,
        patch("app.metrics.QUERY_COST.labels") as mock_query_cost,
    ):
        mock_list.return_value = [mock_run_completed]

        result = await observer_node(base_state)

    assert result["alert_triggered"] is False
    assert result["error_rate"] == 0.0
    assert result["quality_trend"] == "stable"
    assert result["retry_count"] == 1
    assert len(result["execution_trace"]) == 1
    assert result["execution_trace"][0]["node"] == "observer"
    assert result["execution_trace"][0]["status"] == "success"

    # Check that Prometheus labels were set
    mock_agent_cost.assert_called_with(
        agent_name="observer", provider="gemini-flash-3.5"
    )
    mock_agent_latency.assert_called_with(agent_name="observer")
    mock_query_cost.assert_called_with(provider="gemini-flash-3.5")


# ─────────────────────────────────────────────────────────────────────────────
# Threshold breach tests (Latency & Error Rate & Score Trend)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_observer_latency_breach(
    base_state: GraphState, mock_run_completed: MagicMock, mock_db: MagicMock
) -> None:
    """If latency exceeds 3s (3000ms), alert is triggered and rollback initiated."""
    base_state["latency_p95_ms"] = 3500

    with (
        patch("app.graph.nodes.observer.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.observer.EvaluationRepository.list_by_pipeline",
            new_callable=AsyncMock,
        ) as mock_list,
        patch(
            "app.graph.nodes.observer.AuditLogRepository.insert", new_callable=AsyncMock
        ) as mock_audit,
        patch(
            "app.services.deployment_service.DeploymentService.rollback",
            new_callable=AsyncMock,
        ) as mock_rollback,
    ):
        mock_list.return_value = [mock_run_completed]

        result = await observer_node(base_state)

    assert result["alert_triggered"] is True
    assert result["deploy_status"] == "rolled_back"
    assert result["deployment_decision"] == "rollback"
    assert "latency_p95_ms=3500ms" in result["rollback_reason"]

    # Audit log rollback_triggered must be inserted
    mock_audit.assert_called_once()
    assert mock_audit.call_args[1]["event_type"] == "rollback_triggered"
    mock_rollback.assert_called_once()


@pytest.mark.asyncio
async def test_observer_error_rate_breach(
    base_state: GraphState,
    mock_run_completed: MagicMock,
    mock_run_failed: MagicMock,
    mock_db: MagicMock,
) -> None:
    """If error rate exceeds 1% (0.01), rollback is triggered."""
    # 5 runs: 3 completed, 2 failed -> 40% error rate
    runs_history = [
        mock_run_completed,
        mock_run_completed,
        mock_run_completed,
        mock_run_failed,
        mock_run_failed,
    ]

    with (
        patch("app.graph.nodes.observer.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.observer.EvaluationRepository.list_by_pipeline",
            new_callable=AsyncMock,
        ) as mock_list,
        patch(
            "app.graph.nodes.observer.AuditLogRepository.insert", new_callable=AsyncMock
        ) as mock_audit,
        patch(
            "app.services.deployment_service.DeploymentService.rollback",
            new_callable=AsyncMock,
        ) as mock_rollback,
    ):
        mock_list.return_value = runs_history

        result = await observer_node(base_state)

    assert result["error_rate"] == 0.40
    assert result["alert_triggered"] is True
    assert result["deploy_status"] == "rolled_back"
    assert result["deployment_decision"] == "rollback"
    assert "error_rate=40.00%" in result["rollback_reason"]

    mock_audit.assert_called_once()
    assert mock_audit.call_args[1]["event_type"] == "rollback_triggered"
    mock_rollback.assert_called_once()


@pytest.mark.asyncio
async def test_observer_score_drop_breach(
    base_state: GraphState, mock_db: MagicMock
) -> None:
    """If score trend drops by more than 0.10, alert is triggered but no rollback (since latency/errors are fine)."""
    base_state["unified_score"] = 0.70

    prev_run = MagicMock()
    prev_run.run_id = uuid.uuid4()
    prev_run.unified_score = 0.85  # Drop of 0.15
    prev_run.status = "completed"

    with (
        patch("app.graph.nodes.observer.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.observer.EvaluationRepository.list_by_pipeline",
            new_callable=AsyncMock,
        ) as mock_list,
        patch(
            "app.services.deployment_service.DeploymentService.rollback",
            new_callable=AsyncMock,
        ) as mock_rollback,
    ):
        mock_list.return_value = [prev_run]

        result = await observer_node(base_state)

    assert result["quality_trend"] == "degrading"
    assert result["alert_triggered"] is True
    assert result["deploy_status"] is None  # No rollback since p95/errors are safe
    mock_rollback.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Quality trends (improving & stable)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_observer_quality_improving(
    base_state: GraphState, mock_db: MagicMock
) -> None:
    """If score improves vs previous run, quality trend must be 'improving'."""
    base_state["unified_score"] = 0.90

    prev_run = MagicMock()
    prev_run.run_id = uuid.uuid4()
    prev_run.unified_score = 0.80  # Improvement of 0.10
    prev_run.status = "completed"

    with (
        patch("app.graph.nodes.observer.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.observer.EvaluationRepository.list_by_pipeline",
            new_callable=AsyncMock,
        ) as mock_list,
    ):
        mock_list.return_value = [prev_run]

        result = await observer_node(base_state)

    assert result["quality_trend"] == "improving"
    assert result["alert_triggered"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Cost ceiling breach
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_observer_cost_ceiling_breach(
    base_state: GraphState, mock_run_completed: MagicMock, mock_db: MagicMock
) -> None:
    """If query cost exceeds MAX_QUERY_COST_USD, alert is triggered and cost_limit_exceeded audit log written."""
    base_state["cost_per_query_usd"] = (
        0.06  # ceiling is 0.01 in settings config (dev/default)
    )

    with (
        patch("app.graph.nodes.observer.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.observer.EvaluationRepository.list_by_pipeline",
            new_callable=AsyncMock,
        ) as mock_list,
        patch(
            "app.graph.nodes.observer.AuditLogRepository.insert", new_callable=AsyncMock
        ) as mock_audit,
    ):
        mock_list.return_value = [mock_run_completed]

        result = await observer_node(base_state)

    assert result["alert_triggered"] is True

    # Audit log must be inserted for cost limit exceeded
    mock_audit.assert_called_once()
    assert mock_audit.call_args[1]["event_type"] == "cost_limit_exceeded"
