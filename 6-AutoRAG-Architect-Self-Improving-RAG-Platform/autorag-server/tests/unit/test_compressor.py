"""Unit tests for Compressor node — including E-17 TokenGuardrail wiring.

Task E-17: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Rule 80: all critical guardrail paths must have tests.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.state import GraphState
from app.graph.nodes.compressor import compressor_node
from app.services.token_guardrail import TokenBudgetType, TokenCheckResult


def _make_state(**overrides: object) -> GraphState:
    """Minimal GraphState for compressor tests."""
    base = GraphState(
        state_version="v1",
        run_id="run-001",
        pipeline_id="pipe-001",
        organization_id="org-001",
        x_trace_id="trace-001",
        retrieved_chunks=[
            {"content": "chunk one " * 20, "score": 0.9},
            {"content": "chunk two " * 20, "score": 0.8},
            {"content": "chunk three " * 20, "score": 0.7},
        ],
        execution_trace=[],
        guardrail_blocked=False,
        guardrail_block_reason=None,
    )
    base.update(overrides)
    return base


def _allowed_token_result(limit: int = 32000) -> TokenCheckResult:
    return TokenCheckResult(
        allowed=True,
        budget_type=TokenBudgetType.PROMPT,
        requested_tokens=limit,
        budget_limit=limit,
        reason="within token budget",
    )


def _blocked_token_result(requested: int, limit: int) -> TokenCheckResult:
    return TokenCheckResult(
        allowed=False,
        budget_type=TokenBudgetType.PROMPT,
        requested_tokens=requested,
        budget_limit=limit,
        reason=f"prompt tokens {requested} exceeds limit {limit}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# E-17: TokenGuardrail wiring
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compressor_calls_token_guardrail() -> None:
    """E-17: TokenGuardrail.check() must be called before compression."""
    state = _make_state()

    with patch("app.graph.nodes.compressor._token_guardrail.check") as mock_check:
        mock_check.return_value = _allowed_token_result()
        await compressor_node(state)

    mock_check.assert_called_once()
    call_kwargs = mock_check.call_args
    assert call_kwargs.kwargs["budget_type"] == TokenBudgetType.PROMPT
    assert call_kwargs.kwargs["x_trace_id"] == "trace-001"


@pytest.mark.asyncio
async def test_compressor_blocks_when_token_budget_exceeded() -> None:
    """P0.6-2 (13-Jul-2026): a real token-budget breach now actually blocks
    the run (Rule 86 enforcement), instead of silently clamping down and
    continuing as if nothing happened."""
    large_budget = 999_999
    clamped_limit = 32000
    state = _make_state(variant_config={"max_prompt_tokens": large_budget})

    with patch("app.graph.nodes.compressor._token_guardrail.check") as mock_check:
        mock_check.return_value = _blocked_token_result(large_budget, clamped_limit)
        result = await compressor_node(state)

    assert result.get("guardrail_blocked") is True
    assert result.get("guardrail_block_reason") == "policy_violation"
    trace_entry = result["execution_trace"][-1]
    assert trace_entry["status"] == "blocked_token_limit"
    # compressed_context is never populated on a blocked run — nothing to compress
    assert "compressed_context" not in result


@pytest.mark.asyncio
async def test_compressor_skips_when_guardrail_blocked() -> None:
    """Upstream guardrail_blocked=True causes compressor to pass through immediately."""
    state = _make_state(guardrail_blocked=True)

    with patch("app.graph.nodes.compressor._token_guardrail.check") as mock_check:
        result = await compressor_node(state)

    # token guardrail must NOT be called when already blocked upstream
    mock_check.assert_not_called()
    assert result.get("guardrail_blocked") is True


# ─────────────────────────────────────────────────────────────────────────────
# Normal compression flow
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compressor_returns_compressed_context() -> None:
    """Compressor fills compressed_context and token_count."""
    state = _make_state()

    with patch("app.graph.nodes.compressor._token_guardrail.check") as mock_check:
        mock_check.return_value = _allowed_token_result()
        result = await compressor_node(state)

    assert isinstance(result.get("compressed_context"), str)
    assert len(result["compressed_context"]) > 0
    assert isinstance(result.get("token_count"), int)
    assert result["token_count"] > 0


@pytest.mark.asyncio
async def test_compressor_appends_execution_trace() -> None:
    """Compressor must append a trace entry per graph-state-governance Rule 5."""
    state = _make_state()

    with patch("app.graph.nodes.compressor._token_guardrail.check") as mock_check:
        mock_check.return_value = _allowed_token_result()
        result = await compressor_node(state)

    trace = result.get("execution_trace", [])
    assert len(trace) == 1
    entry = trace[0]
    assert entry["node"] == "compressor"
    assert entry["x_trace_id"] == "trace-001"
    assert "latency_ms" in entry


@pytest.mark.asyncio
async def test_compressor_handles_empty_chunks() -> None:
    """No chunks → compressed_context is empty string, no crash."""
    state = _make_state(retrieved_chunks=[])

    with patch("app.graph.nodes.compressor._token_guardrail.check") as mock_check:
        mock_check.return_value = _allowed_token_result()
        result = await compressor_node(state)

    assert result.get("compressed_context") == ""
    assert result.get("token_count") == 0
