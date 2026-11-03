"""Unit tests for Agent 2 — Query Rewriter node.

Task E-7: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Rule 80: all critical node paths must have tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.state import GraphState
from app.graph.nodes.query_rewriter import query_rewriter_node
from app.services.llm_service import LLMProviderError, LLMResponse

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def base_state() -> GraphState:
    return GraphState(
        state_version="v1",
        run_id="run-001",
        pipeline_id="pipe-001",
        organization_id="org-001",
        x_trace_id="trace-abc",
        raw_query="what is machine learning",
        execution_trace=[],
        guardrail_blocked=False,
        guardrail_block_reason=None,
    )


@pytest.fixture
def mock_llm_response() -> LLMResponse:
    return LLMResponse(
        content="What is machine learning and how does supervised learning differ from unsupervised learning?",
        provider="gemini-flash-3.5",
        prompt_tokens=45,
        completion_tokens=22,
        total_tokens=67,
        cost_usd=0.000005,
        latency_ms=110,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rewritten_query_differs_from_raw(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """Node must write a rewritten_query that is different from raw_query."""
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        result = await query_rewriter_node(base_state)

    assert result["rewritten_query"] != base_state["raw_query"]
    assert "machine learning" in result["rewritten_query"]


@pytest.mark.asyncio
async def test_execution_trace_appended(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """Node must append exactly one execution_trace entry."""
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        result = await query_rewriter_node(base_state)

    trace = result["execution_trace"]
    assert len(trace) == 1
    entry = trace[0]
    assert entry["node"] == "query_rewriter"
    assert entry["status"] == "success"
    assert entry["x_trace_id"] == "trace-abc"
    assert "latency_ms" in entry


@pytest.mark.asyncio
async def test_execution_trace_contains_cost_fields(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """Rule 86: execution_trace must carry cost_usd, provider, prompt_tokens, completion_tokens."""
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        result = await query_rewriter_node(base_state)

    entry = result["execution_trace"][0]
    assert entry["cost_usd"] == mock_llm_response.cost_usd
    assert entry["provider"] == "gemini-flash-3.5"
    assert entry["prompt_tokens"] == mock_llm_response.prompt_tokens
    assert entry["completion_tokens"] == mock_llm_response.completion_tokens


@pytest.mark.asyncio
async def test_x_trace_id_propagated(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """x_trace_id must be unchanged in the returned state and in execution_trace."""
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        result = await query_rewriter_node(base_state)

    assert result["x_trace_id"] == "trace-abc"
    assert result["execution_trace"][0]["x_trace_id"] == "trace-abc"


@pytest.mark.asyncio
async def test_existing_execution_trace_entries_preserved(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """Node must append to execution_trace — not overwrite prior entries."""
    prior_entry = {
        "node": "ingestion",
        "timestamp": "2026-06-25T00:00:00+00:00",
        "x_trace_id": "trace-abc",
        "graph_state_version": "v1",
        "latency_ms": 50,
        "status": "success",
        "retry_count": 0,
    }
    state_with_trace = GraphState(**{**dict(base_state), "execution_trace": [prior_entry]})

    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        result = await query_rewriter_node(state_with_trace)

    assert len(result["execution_trace"]) == 2
    assert result["execution_trace"][0]["node"] == "ingestion"
    assert result["execution_trace"][1]["node"] == "query_rewriter"


# ─────────────────────────────────────────────────────────────────────────────
# Guardrail blocked passthrough
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guardrail_blocked_state_passes_through(base_state: GraphState) -> None:
    """If guardrail_blocked=True, node must return state unchanged — no LLM call."""
    blocked_state = GraphState(
        **{**dict(base_state), "guardrail_blocked": True, "guardrail_block_reason": "pii_detected"}
    )

    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
    ) as mock_call:
        result = await query_rewriter_node(blocked_state)

    mock_call.assert_not_called()
    assert result["guardrail_blocked"] is True
    assert result.get("rewritten_query") is None


# ─────────────────────────────────────────────────────────────────────────────
# LLM provider failure — fallback to original query
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_providers_fail_falls_back_to_raw_query(
    base_state: GraphState,
) -> None:
    """If all LLM providers fail, rewritten_query must equal raw_query (spec fallback)."""
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        side_effect=LLMProviderError("All providers exhausted"),
    ):
        result = await query_rewriter_node(base_state)

    assert result["rewritten_query"] == base_state["raw_query"]


@pytest.mark.asyncio
async def test_all_providers_fail_trace_status_is_failed(
    base_state: GraphState,
) -> None:
    """On provider failure, execution_trace status must be 'failed'."""
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        side_effect=LLMProviderError("All providers exhausted"),
    ):
        result = await query_rewriter_node(base_state)

    entry = result["execution_trace"][0]
    assert entry["status"] == "failed"
    assert entry["provider"] == "none"
    assert entry["cost_usd"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Rewrite mode derivation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_f03_failure_type_uses_clarify_mode(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """F-03 (Hallucination) failure_type must trigger 'clarify' rewrite mode."""
    state_f03 = GraphState(**{**dict(base_state), "failure_type": "F-03"})

    captured_prompt: list[str] = []

    async def capture_call(
        prompt: str,
        x_trace_id: str,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        captured_prompt.append(prompt)
        return mock_llm_response

    with patch("app.graph.nodes.query_rewriter._llm.call", side_effect=capture_call):
        await query_rewriter_node(state_f03)

    assert len(captured_prompt) == 1
    assert "clarify" in captured_prompt[0]


@pytest.mark.asyncio
async def test_no_failure_type_uses_expand_mode(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """Default (no failure_type) must use 'expand' rewrite mode."""
    captured_prompt: list[str] = []

    async def capture_call(
        prompt: str,
        x_trace_id: str,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        captured_prompt.append(prompt)
        return mock_llm_response

    with patch("app.graph.nodes.query_rewriter._llm.call", side_effect=capture_call):
        await query_rewriter_node(base_state)

    assert len(captured_prompt) == 1
    assert "expand" in captured_prompt[0]


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_llm_response_falls_back_to_raw_query(
    base_state: GraphState,
) -> None:
    """If LLM returns empty string, node must fall back to raw_query."""
    empty_response = LLMResponse(
        content="",
        provider="gemini-flash-3.5",
        prompt_tokens=40,
        completion_tokens=0,
        total_tokens=40,
        cost_usd=0.000003,
        latency_ms=80,
    )
    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=empty_response,
    ):
        result = await query_rewriter_node(base_state)

    assert result["rewritten_query"] == base_state["raw_query"]


@pytest.mark.asyncio
async def test_node_does_not_mutate_unowned_fields(
    base_state: GraphState,
    mock_llm_response: LLMResponse,
) -> None:
    """Node must not overwrite fields owned by other agents (governance Rule 2)."""
    state_with_score = GraphState(
        **{**dict(base_state), "unified_score": 0.91, "failure_type": "F-01"}
    )

    with patch(
        "app.graph.nodes.query_rewriter._llm.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        result = await query_rewriter_node(state_with_score)

    assert result["unified_score"] == 0.91
    assert result["failure_type"] == "F-01"
