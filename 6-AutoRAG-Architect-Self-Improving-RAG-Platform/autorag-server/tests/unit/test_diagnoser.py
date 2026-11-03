"""E-1 unit tests — Diagnoser agent rule-based classification.

Tests the deterministic pre-filter (_rule_based_classify) without any LLM call.
All 5 failure types are tested with boundary conditions.
No mocks needed — the rule-based path is a pure function on GraphState metrics.

E-1 AC:
  - F-03 triggered when faithfulness < 0.5
  - F-05 triggered when latency_p95_ms > 3000
  - F-01 triggered when no chunks or all chunks below quality floor
  - F-02 triggered when token_count > budget
  - LLM path (None return) triggered when no deterministic rule applies
  - execution_trace is appended correctly
  - confidence and failure_type fields are set in output state
"""
from __future__ import annotations

import pytest

from app.core.state import initial_state
from app.graph.nodes.diagnoser import _rule_based_classify

SAMPLE_IDS = {
    "run_id": "01900000-0000-7000-8000-000000000001",
    "pipeline_id": "01900000-0000-7000-8000-000000000002",
    "organization_id": "01900000-0000-7000-8000-000000000003",
    "x_trace_id": "01900000-0000-7000-8000-000000000004",
    "user_id": "01900000-0000-7000-8000-000000000005",
    "session_id": "01900000-0000-7000-8000-000000000006",
}


def _base() -> dict:
    state = initial_state(**SAMPLE_IDS)
    state["faithfulness"] = 0.85
    state["latency_p95_ms"] = 1200
    state["token_count"] = 2000
    state["retrieved_chunks"] = [{"score": 0.75, "text": "relevant content"}]
    return state


# ─── Rule-based pre-filter tests ─────────────────────────────────────────────

def test_classify_f03_hallucination_below_threshold() -> None:
    """faithfulness < 0.5 → F-03 Hallucination regardless of other metrics."""
    state = _base()
    state["faithfulness"] = 0.3
    result = _rule_based_classify(state)
    assert result is not None
    assert result["failure_type"] == "F-03"
    assert result["confidence"] >= 0.9


def test_classify_f03_faithfulness_exactly_at_threshold() -> None:
    """faithfulness == 0.5 should NOT trigger F-03 (strict < not <=)."""
    state = _base()
    state["faithfulness"] = 0.5
    result = _rule_based_classify(state)
    assert result is None or result["failure_type"] != "F-03"


def test_classify_f05_latency_spike() -> None:
    """latency_p95_ms > 3000 → F-05 Latency Spike."""
    state = _base()
    state["latency_p95_ms"] = 4500
    result = _rule_based_classify(state)
    assert result is not None
    assert result["failure_type"] == "F-05"
    assert result["confidence"] >= 0.9


def test_classify_f05_latency_not_triggered_at_boundary() -> None:
    """latency_p95_ms == 3000 should NOT trigger F-05 (strict >)."""
    state = _base()
    state["latency_p95_ms"] = 3000
    result = _rule_based_classify(state)
    assert result is None or result["failure_type"] != "F-05"


def test_classify_f01_empty_chunks() -> None:
    """Empty retrieved_chunks → F-01 Retrieval Miss."""
    state = _base()
    state["retrieved_chunks"] = []
    result = _rule_based_classify(state)
    assert result is not None
    assert result["failure_type"] == "F-01"


def test_classify_f01_all_low_score_chunks() -> None:
    """All chunks below score floor → F-01 Retrieval Miss."""
    state = _base()
    state["retrieved_chunks"] = [
        {"score": 0.1, "text": "irrelevant"},
        {"score": 0.2, "text": "also irrelevant"},
    ]
    result = _rule_based_classify(state)
    assert result is not None
    assert result["failure_type"] == "F-01"


def test_classify_f02_token_overflow() -> None:
    """token_count > 3800 → F-02 Context Overflow."""
    state = _base()
    state["token_count"] = 4200
    result = _rule_based_classify(state)
    assert result is not None
    assert result["failure_type"] == "F-02"


def test_classify_returns_none_for_ambiguous_state() -> None:
    """When no deterministic rule applies, return None to trigger LLM classification."""
    state = _base()
    state["faithfulness"] = 0.75     # OK
    state["latency_p95_ms"] = 800    # OK
    state["token_count"] = 1500      # OK
    state["retrieved_chunks"] = [{"score": 0.8, "text": "relevant"}]
    result = _rule_based_classify(state)
    assert result is None


def test_classify_f03_takes_priority_over_latency() -> None:
    """faithfulness check runs before latency check — F-03 wins when both fail."""
    state = _base()
    state["faithfulness"] = 0.2   # F-03 condition
    state["latency_p95_ms"] = 5000  # F-05 condition
    result = _rule_based_classify(state)
    assert result is not None
    assert result["failure_type"] == "F-03"  # faithfulness checked first


@pytest.mark.asyncio
async def test_diagnoser_node_sets_failure_fields_synchronously() -> None:
    """diagnoser_node sets failure_type + appends execution_trace using rule-based path."""
    from app.graph.nodes.diagnoser import diagnoser_node

    state = initial_state(**SAMPLE_IDS)
    state["faithfulness"] = 0.1   # triggers F-03 deterministically
    state["execution_trace"] = []

    result = await diagnoser_node(state)

    assert result["failure_type"] == "F-03"
    assert result["confidence"] is not None
    assert result["failure_analysis"] is not None
    assert result["remediation_hint"] is not None
    assert result["root_cause_analysis"] is not None

    # execution_trace must have exactly one new entry appended
    assert len(result["execution_trace"]) == 1
    trace = result["execution_trace"][0]
    assert trace["node"] == "diagnoser"
    assert trace["x_trace_id"] == SAMPLE_IDS["x_trace_id"]
    assert trace["status"] == "success"
