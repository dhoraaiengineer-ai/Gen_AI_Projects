"""E-2 unit tests -- Improver agent variant generation.

Tests the deterministic playbook and _apply_delta without any LLM call.
Each failure type maps to predictable hyperparameter adjustments.

E-2 AC verified:
  - All 5 failure types (F-01 to F-05) are present in the playbook
  - _apply_delta applies numeric deltas additively and string deltas as replacements
  - improver_node increments improvement_attempt
  - improver_node appends to execution_trace with node=improver
  - improver_node sets variant_config and variant_id
"""
from __future__ import annotations

import pytest

from app.core.state import initial_state
from app.graph.nodes.improver import _VARIANT_PLAYBOOK, _apply_delta

SAMPLE_IDS = {
    "run_id": "01900000-0000-7000-8000-000000000001",
    "pipeline_id": "01900000-0000-7000-8000-000000000002",
    "organization_id": "01900000-0000-7000-8000-000000000003",
    "x_trace_id": "01900000-0000-7000-8000-000000000004",
    "user_id": "01900000-0000-7000-8000-000000000005",
    "session_id": "01900000-0000-7000-8000-000000000006",
}

_BASE_CONFIG = {"k_value": 10, "chunk_size": 512}


# -- Playbook structure tests (synchronous, no I/O) ---------------------------

def test_all_failure_types_present() -> None:
    """All 5 failure types must have entries in the playbook."""
    for code in ("F-01", "F-02", "F-03", "F-04", "F-05"):
        assert code in _VARIANT_PLAYBOOK, f"Missing playbook entry for {code}"


def test_each_failure_type_has_three_variants() -> None:
    """Each failure type must provide exactly 3 variant deltas."""
    for code, deltas in _VARIANT_PLAYBOOK.items():
        assert len(deltas) == 3, f"{code}: expected 3 deltas, got {len(deltas)}"


def test_apply_delta_adds_numeric_values() -> None:
    """Numeric deltas are added to the base value."""
    result = _apply_delta({"k_value": 10}, {"k_value": 5})
    assert result["k_value"] == 15


def test_apply_delta_replaces_string_values() -> None:
    """String deltas replace the base value entirely."""
    result = _apply_delta({"chunk_strategy": "semantic"}, {"chunk_strategy": "hierarchical"})
    assert result["chunk_strategy"] == "hierarchical"


def test_apply_delta_clamps_numeric_to_minimum_1() -> None:
    """Negative delta that would reduce below 1 is clamped to 1."""
    result = _apply_delta({"k_value": 2}, {"k_value": -10})
    assert result["k_value"] == 1


def test_apply_delta_preserves_untouched_keys() -> None:
    """Keys not in the delta are carried forward unchanged."""
    result = _apply_delta({"k_value": 10, "overlap": 64}, {"k_value": 5})
    assert result["overlap"] == 64


def test_f01_increases_k_value() -> None:
    """F-01 (retrieval failure): at least one variant increases k_value."""
    deltas = _VARIANT_PLAYBOOK["F-01"]
    k_variants = [_apply_delta(_BASE_CONFIG, d) for d in deltas]
    assert any(v.get("k_value", 10) > _BASE_CONFIG["k_value"] for v in k_variants)


def test_f02_decreases_k_or_chunk_size() -> None:
    """F-02 (hallucination): at least one variant reduces k_value or chunk_size."""
    deltas = _VARIANT_PLAYBOOK["F-02"]
    variants = [_apply_delta(_BASE_CONFIG, d) for d in deltas]
    assert any(
        v.get("k_value", 10) < _BASE_CONFIG["k_value"]
        or v.get("chunk_size", 512) < _BASE_CONFIG["chunk_size"]
        for v in variants
    )


def test_f04_increases_chunk_size() -> None:
    """F-04 (cost explosion): at least one variant increases chunk_size."""
    deltas = _VARIANT_PLAYBOOK["F-04"]
    variants = [_apply_delta(_BASE_CONFIG, d) for d in deltas]
    assert any(v.get("chunk_size", 512) > _BASE_CONFIG["chunk_size"] for v in variants)


def test_f05_decreases_k_or_chunk_size() -> None:
    """F-05 (prompt injection): at least one variant reduces k_value or chunk_size."""
    deltas = _VARIANT_PLAYBOOK["F-05"]
    variants = [_apply_delta(_BASE_CONFIG, d) for d in deltas]
    assert any(
        v.get("k_value", 10) < _BASE_CONFIG["k_value"]
        or v.get("chunk_size", 512) < _BASE_CONFIG["chunk_size"]
        for v in variants
    )


# -- Full async node integration tests ----------------------------------------

@pytest.mark.asyncio
async def test_improver_node_returns_variant_config() -> None:
    """improver_node sets variant_config and variant_id in state."""
    from app.graph.nodes.improver import improver_node

    state = initial_state(**SAMPLE_IDS)
    state["failure_type"] = "F-01"
    state["execution_trace"] = []

    result = await improver_node(state)

    assert result["variant_config"] is not None
    assert result["variant_id"] is not None


@pytest.mark.asyncio
async def test_improver_node_increments_improvement_attempt() -> None:
    """improvement_attempt increments by 1 each call."""
    from app.graph.nodes.improver import improver_node

    state = initial_state(**SAMPLE_IDS)
    state["failure_type"] = "F-01"
    state["execution_trace"] = []
    state["improvement_attempt"] = 0

    result = await improver_node(state)
    assert result["improvement_attempt"] == 1

    state2 = {**result, "failure_type": "F-02"}
    result2 = await improver_node(state2)
    assert result2["improvement_attempt"] == 2


@pytest.mark.asyncio
async def test_improver_node_appends_execution_trace() -> None:
    """execution_trace gets one entry from improver with correct node name."""
    from app.graph.nodes.improver import improver_node

    state = initial_state(**SAMPLE_IDS)
    state["failure_type"] = "F-02"
    state["execution_trace"] = [{"node": "diagnoser", "status": "success"}]

    result = await improver_node(state)

    assert len(result["execution_trace"]) == 2
    latest = result["execution_trace"][-1]
    assert latest["node"] == "improver"
    assert latest["x_trace_id"] == SAMPLE_IDS["x_trace_id"]
    assert latest["status"] == "success"
    assert "cost_usd" in latest and latest["cost_usd"] == 0.0
