"""Unit tests for LangGraph conditional edge routing functions.

Spec: .claude/rules/80-testing-quality.md — 90% coverage of all conditional edges required.

P0.5 fix (12-Jul-2026): this file previously imported from `app.graph.workflow`, a dead
scaffold (mostly `_noop_node` stubs, `route_after_evaluation` returning route names like
"approve"/"hitl_approval"/"diagnose" that don't exist anywhere in the real graph) that
nothing in production ever imported -- `build_autorag_graph()` in `app.core.workflow` is
the actual live graph. That decoy module has been deleted; this file now tests the real
routing functions via their public aliases. `_route_after_evaluator` and `_route_after_observer`
branch coverage also exists in `tests/unit/test_retry_routing.py` (D-9) -- this file adds the
`_route_after_deployer` coverage that file doesn't have, plus keeps the evaluator/observer
cases for readability of the full conditional-edge surface in one place.
"""

from langgraph.graph import END

from app.core.state import GraphState
from app.core.workflow import (
    route_after_deployment,
    route_after_diagnosis,
    route_after_evaluation,
)


class TestRouteAfterEvaluation:
    def test_high_score_routes_to_deployer(self) -> None:
        """Score >= 0.85 with full adversarial pass -> deployer."""
        state: GraphState = {
            "unified_score": 0.90,
            "faithfulness": 0.85,
            "adversarial_pass_rate": 1.0,
        }
        assert route_after_evaluation(state) == "deployer"

    def test_hitl_range_routes_to_hitl(self) -> None:
        """Score 0.70-0.84 with good faithfulness -> hitl (human approval)."""
        state: GraphState = {
            "unified_score": 0.75,
            "faithfulness": 0.80,
            "adversarial_pass_rate": 1.0,
        }
        assert route_after_evaluation(state) == "hitl"

    def test_hitl_lower_boundary_routes_to_hitl(self) -> None:
        state: GraphState = {
            "unified_score": 0.70,
            "faithfulness": 0.80,
            "adversarial_pass_rate": 1.0,
        }
        assert route_after_evaluation(state) == "hitl"

    def test_score_below_07_routes_to_observer(self) -> None:
        """Score < 0.70 (faithfulness/adversarial OK) -> observer (retry loop entry)."""
        state: GraphState = {
            "unified_score": 0.60,
            "faithfulness": 0.80,
            "adversarial_pass_rate": 1.0,
        }
        assert route_after_evaluation(state) == "observer"

    def test_faithfulness_hard_block_routes_to_end(self) -> None:
        """Faithfulness < 0.5 is a non-bypassable hard block -> END, not the retry loop."""
        state: GraphState = {
            "unified_score": 0.95,
            "faithfulness": 0.40,
            "adversarial_pass_rate": 1.0,
        }
        assert route_after_evaluation(state) == END

    def test_adversarial_fail_routes_to_end(self) -> None:
        """adversarial_pass_rate < 1.0 blocks deployment regardless of score -> END."""
        state: GraphState = {
            "unified_score": 0.90,
            "faithfulness": 0.85,
            "adversarial_pass_rate": 0.9,
        }
        assert route_after_evaluation(state) == END

    def test_missing_state_fields_default_to_end(self) -> None:
        """Empty state -- faithfulness/pass_rate default to None -> hard block -> END."""
        state: GraphState = {}
        assert route_after_evaluation(state) == END


class TestRouteAfterDeployment:
    def test_default_routes_to_end(self) -> None:
        state: GraphState = {"deploy_status": "success"}
        assert route_after_deployment(state) == END

    def test_rolled_back_routes_to_observer(self) -> None:
        """Auto-rollback resumes Observer monitoring, not a dedicated notify node."""
        state: GraphState = {"deploy_status": "rolled_back", "rollback_reason": "error_rate > 1%"}
        assert route_after_deployment(state) == "observer"

    def test_failed_routes_to_end(self) -> None:
        state: GraphState = {"deploy_status": "failed"}
        assert route_after_deployment(state) == END

    def test_missing_deploy_status_routes_to_end(self) -> None:
        state: GraphState = {}
        assert route_after_deployment(state) == END


# route_after_diagnosis is actually `_route_after_observer` (retry-count based, not
# failure_type based -- Diagnoser itself has no conditional edge in the real graph,
# it always proceeds to Improver). Kept under this name since it's the public alias
# `app.core.workflow.route_after_diagnosis` exposes.
class TestRouteAfterDiagnosis:
    def test_retries_remaining_routes_to_diagnoser(self) -> None:
        state: GraphState = {"retry_count": 1, "max_retries": 3}
        assert route_after_diagnosis(state) == "diagnoser"

    def test_max_retries_reached_routes_to_end(self) -> None:
        state: GraphState = {"retry_count": 3, "max_retries": 3}
        assert route_after_diagnosis(state) == END

    def test_default_max_retries_is_three(self) -> None:
        """max_retries omitted -> defaults to 3."""
        state: GraphState = {"retry_count": 3}
        assert route_after_diagnosis(state) == END
