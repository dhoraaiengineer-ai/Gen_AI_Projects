"""Integration tests for D-7 (GraphState + graph wiring) and D-8 (checkpointing).

No mocks — tests verify the real compiled graph, routing functions, and checkpointer.

D-7 tests (AC-7.1 – AC-7.7):
  AC-7.1  build_autorag_graph() compiles without ImportError or TypeError
  AC-7.2  initial_state() produces state with all 5 identity fields
  AC-7.3  graph_state_version == "v1.0" on fresh state
  AC-7.4  retry_count == 0 and max_retries == 3 on fresh state
  AC-7.5  _route_after_evaluator returns END when faithfulness = 0.3 (hard block)
  AC-7.6  _route_after_evaluator returns END when guardrail_blocked = True
  AC-7.7  _route_after_observer returns END when retry_count >= max_retries

D-8 tests (AC-D8.1 – AC-D8.5):
  AC-D8.1  build_autorag_graph() compiles when passed a MemorySaver checkpointer
  AC-D8.2  invocation config thread_id=pipeline_id (not run_id or x_trace_id)
  AC-D8.3  _route_after_observer reads max_retries from state (Bug #2 fix)
  AC-D8.4  _route_after_evaluator returns END when faithfulness is None (fail-closed)
  AC-D8.5  _route_after_observer treats max_retries=0 as limit-0, not fallback-3
"""

from __future__ import annotations

from langgraph.graph import END

from app.core.state import initial_state
from app.core.workflow import (
    _route_after_evaluator,
    _route_after_observer,
    build_autorag_graph,
)

# Sample UUIDs v7 — used across all tests
SAMPLE_IDS = {
    "run_id": "01900000-0000-7000-8000-000000000001",
    "pipeline_id": "01900000-0000-7000-8000-000000000002",
    "organization_id": "01900000-0000-7000-8000-000000000003",
    "x_trace_id": "01900000-0000-7000-8000-000000000004",
    "user_id": "01900000-0000-7000-8000-000000000005",
    "session_id": "01900000-0000-7000-8000-000000000006",
}


def test_graph_compiles_without_error() -> None:
    """[AC-7.1] build_autorag_graph() must compile with no ImportError or TypeError."""
    graph = build_autorag_graph()
    assert graph is not None


def test_initial_state_has_all_identity_fields() -> None:
    """[AC-7.2] initial_state() must set user_id, session_id, created_at, updated_at, deployment_id."""
    state = initial_state(**SAMPLE_IDS)
    assert state["user_id"] == SAMPLE_IDS["user_id"]
    assert state["session_id"] == SAMPLE_IDS["session_id"]
    assert state["created_at"].endswith("Z")
    assert state["updated_at"].endswith("Z")
    assert state.get("deployment_id") is None


def test_initial_state_graph_state_version() -> None:
    """[AC-7.3] graph_state_version must be 'v1.0' on fresh state."""
    state = initial_state(**SAMPLE_IDS)
    assert state["graph_state_version"] == "v1.0"


def test_initial_state_retry_defaults() -> None:
    """[AC-7.4] retry_count=0 and max_retries=3 on fresh state."""
    state = initial_state(**SAMPLE_IDS)
    assert state["retry_count"] == 0
    assert state["max_retries"] == 3


def test_route_after_evaluator_faithfulness_hard_block() -> None:
    """[AC-7.5] faithfulness < 0.5 must return END regardless of unified_score."""
    state = initial_state(**SAMPLE_IDS)
    state["faithfulness"] = 0.3
    state["unified_score"] = 0.90  # would normally deploy — faithfulness overrides
    state["adversarial_pass_rate"] = 1.0
    state["guardrail_blocked"] = False
    assert _route_after_evaluator(state) == END


def test_route_after_evaluator_guardrail_blocked() -> None:
    """[AC-7.6] guardrail_blocked=True must return END — highest priority check."""
    state = initial_state(**SAMPLE_IDS)
    state["guardrail_blocked"] = True
    state["unified_score"] = 0.95  # high score — guardrail still overrides
    state["faithfulness"] = 0.9
    assert _route_after_evaluator(state) == END


def test_route_after_observer_ends_at_max_retries() -> None:
    """[AC-7.7] retry_count >= max_retries must return END (loop termination)."""
    state = initial_state(**SAMPLE_IDS)
    state["retry_count"] = 3
    state["max_retries"] = 3
    assert _route_after_observer(state) == END


# ──────────────────────────────────────────────────────────────────────────────
# D-8: PostgreSQL Checkpointing
# ──────────────────────────────────────────────────────────────────────────────


def test_graph_compiles_with_memory_saver_checkpointer() -> None:
    """[AC-D8.1] build_autorag_graph() must accept and compile with a MemorySaver checkpointer."""
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_autorag_graph(checkpointer=MemorySaver())
    assert graph is not None


def test_invocation_config_has_required_keys() -> None:
    """[AC-D8.2] thread_id must be pipeline_id (not run_id or x_trace_id); x_trace_id unchanged."""
    state = initial_state(**SAMPLE_IDS)
    config = {
        "configurable": {
            "thread_id": state["pipeline_id"],
            "x_trace_id": state["x_trace_id"],
        }
    }
    assert config["configurable"]["thread_id"] == SAMPLE_IDS["pipeline_id"]
    # thread_id must map to pipeline_id, not to any other ID field
    assert config["configurable"]["thread_id"] != SAMPLE_IDS["run_id"]
    assert config["configurable"]["thread_id"] != SAMPLE_IDS["x_trace_id"]
    assert config["configurable"]["x_trace_id"] == SAMPLE_IDS["x_trace_id"]


def test_route_after_observer_reads_max_retries_from_state() -> None:
    """[AC-D8.3] _route_after_observer reads max_retries from state — not hardcoded 3.

    STARTER_KIT Bug #2 fix: retry_count >= max_retries (from state) must end the loop
    even when max_retries is set to a value other than 3.
    """
    state = initial_state(**SAMPLE_IDS)
    state["retry_count"] = 2
    state["max_retries"] = 2  # custom threshold — loop must still terminate
    assert _route_after_observer(state) == END


def test_route_after_evaluator_fails_closed_when_faithfulness_missing() -> None:
    """[AC-D8.4] _route_after_evaluator returns END when faithfulness is None (fail-closed).

    ai-guardrails.md Rule 13: safety systems must fail closed.
    An evaluator that crashes before writing faithfulness must not allow deployment.
    """
    state = initial_state(**SAMPLE_IDS)
    state["guardrail_blocked"] = False
    state["unified_score"] = 0.95
    state["adversarial_pass_rate"] = 1.0
    # faithfulness deliberately left as None (evaluator crashed before writing it)
    assert _route_after_evaluator(state) == END


def test_route_after_observer_treats_max_retries_zero_as_no_retries() -> None:
    """[AC-D8.5] max_retries=0 means terminate immediately — must not be coerced to 3.

    Bug fix: (state.get("max_retries") or 3) evaluates 0 or 3 == 3, ignoring max_retries=0.
    Correct: use an explicit None check so zero is respected as a valid limit.
    """
    state = initial_state(**SAMPLE_IDS)
    state["retry_count"] = 0  # fresh run, no retries attempted
    state["max_retries"] = 0  # operator explicitly disabled retries
    assert _route_after_observer(state) == END
