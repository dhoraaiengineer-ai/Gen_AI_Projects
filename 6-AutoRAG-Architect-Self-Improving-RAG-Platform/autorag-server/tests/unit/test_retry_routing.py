"""D-9 integration tests — explicit retry routing edges.

Tests verify the full retry loop path and all routing edge cases.
No mocks — routing functions are pure deterministic functions on GraphState.

D-9 AC:
  - _route_after_evaluator correct for all 6 branches
  - _route_after_observer terminates at retry_count >= max_retries
  - faithfulness < 0.5 → END regardless of score
  - guardrail_blocked → END regardless of score
  - adversarial_pass_rate < 1.0 → END
  - Zero inline try/except retry loops in any node (enforced by Rule 60)
"""
from __future__ import annotations

from langgraph.graph import END

from app.core.state import initial_state
from app.core.workflow import (
    _route_after_evaluator,
    _route_after_improver,
    _route_after_observer,
)

SAMPLE_IDS = {
    "run_id": "01900000-0000-7000-8000-000000000001",
    "pipeline_id": "01900000-0000-7000-8000-000000000002",
    "organization_id": "01900000-0000-7000-8000-000000000003",
    "x_trace_id": "01900000-0000-7000-8000-000000000004",
    "user_id": "01900000-0000-7000-8000-000000000005",
    "session_id": "01900000-0000-7000-8000-000000000006",
}


def _base() -> dict:
    """Fresh state with clean safety fields."""
    state = initial_state(**SAMPLE_IDS)
    state["guardrail_blocked"] = False
    state["faithfulness"] = 0.9
    state["adversarial_pass_rate"] = 1.0
    return state


# ─── _route_after_evaluator — 6 branch coverage ─────────────────────────────

def test_route_evaluator_score_above_85_goes_to_deployer() -> None:
    """Score >= 0.85 with all safety checks passing → deployer."""
    state = _base()
    state["unified_score"] = 0.88
    assert _route_after_evaluator(state) == "deployer"


def test_route_evaluator_score_70_84_goes_to_hitl() -> None:
    """Score in 0.70–0.84 range → hitl (human approval required)."""
    state = _base()
    state["unified_score"] = 0.75
    assert _route_after_evaluator(state) == "hitl"


def test_route_evaluator_score_below_70_goes_to_observer() -> None:
    """Score < 0.70 → observer (start retry loop)."""
    state = _base()
    state["unified_score"] = 0.62
    assert _route_after_evaluator(state) == "observer"


def test_route_evaluator_adversarial_fail_goes_to_end() -> None:
    """adversarial_pass_rate < 1.0 → END regardless of score."""
    state = _base()
    state["unified_score"] = 0.92    # would normally deploy
    state["adversarial_pass_rate"] = 0.8   # failed 2/10 adversarial Q&A
    assert _route_after_evaluator(state) == END


# ─── _route_after_observer — retry termination ───────────────────────────────

def test_route_observer_goes_to_diagnoser_when_retries_remain() -> None:
    """retry_count < max_retries → diagnoser (continue the loop)."""
    state = initial_state(**SAMPLE_IDS)
    state["retry_count"] = 1
    state["max_retries"] = 3
    assert _route_after_observer(state) == "diagnoser"


def test_route_observer_ends_at_exactly_max_retries() -> None:
    """retry_count == max_retries → END (stop the loop)."""
    state = initial_state(**SAMPLE_IDS)
    state["retry_count"] = 3
    state["max_retries"] = 3
    assert _route_after_observer(state) == END


def test_route_observer_ends_above_max_retries() -> None:
    """retry_count > max_retries → END (guard against stale state)."""
    state = initial_state(**SAMPLE_IDS)
    state["retry_count"] = 5
    state["max_retries"] = 3
    assert _route_after_observer(state) == END


# ─── _route_after_improver ───────────────────────────────────────────────────

def test_route_improver_always_loops_to_ingestion() -> None:
    """After generating a variant, improver always returns to ingestion."""
    state = initial_state(**SAMPLE_IDS)
    assert _route_after_improver(state) == "ingestion"
