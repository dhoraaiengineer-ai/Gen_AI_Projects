"""P0.5-4 — closed-loop branch proof via controlled backend fixtures.

The live golden-path rerun (verification/releases/v4.0/P0_5_GOLDEN_PATH_EVIDENCE_12JUL2026.md)
scored 0.8489 on a real query against the real Attention paper and correctly routed to
HITL approval, NOT into the Observer -> Diagnoser -> Improver retry loop -- that's the
correct, valid outcome for a real run that legitimately scores well. Per the plan's own
rule, that success must not be forced into a failure to "prove" the retry loop.

This file proves the two closed-loop branches separately, via real node functions and
real GraphState fixtures (no LLM/service mocking), never by forcing the live document run:

  - Pass branch:    a well-scoring evaluation routes straight to Deployer, not the retry loop.
  - Failure branch: a genuinely low-scoring-but-faithful evaluation (the honest "answer
                     incomplete" case, not hallucination) is chased through the real
                     Observer -> Diagnoser -> Improver node chain, proving state threads
                     correctly and all 3 Improver candidates are persisted.

Real network calls happen here (Diagnoser's LLM classification call is not mocked --
Rule 80: "Mocking the entire RAG pipeline hides retrieval bugs") -- this is an
integration test, not a unit test.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.state import initial_state

# NOTE: `route_after_diagnosis` is the confusingly-named public alias in
# app.core.workflow for `_route_after_observer` (retry-count based routing
# that runs after Observer, not Diagnoser -- Diagnoser itself has no
# conditional edge, it always proceeds straight to Improver). Imported under
# its real name for clarity here rather than perpetuating the confusion.
from app.core.workflow import route_after_diagnosis as route_after_observer
from app.core.workflow import route_after_evaluation
from app.graph.nodes.diagnoser import diagnoser_node
from app.graph.nodes.improver import improver_node
from app.graph.nodes.observer import observer_node

# Real seeded local-dev IDs (see app/main.py startup seed) -- valid UUIDs so
# Observer's historical-run lookup query executes cleanly even with no matches.
_ORG_ID = "00000000-0000-0000-0000-000000000001"
_PIPELINE_ID = "01960000-0000-7000-8000-000000000001"


def _sample_ids() -> dict[str, str]:
    return {
        "run_id": str(uuid.uuid4()),
        "pipeline_id": _PIPELINE_ID,
        "organization_id": _ORG_ID,
        "x_trace_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
    }


class TestPassBranch:
    """A well-scoring evaluation must route to Deployer, never the retry loop."""

    def test_high_score_faithful_run_routes_to_deployer_not_observer(self) -> None:
        state = initial_state(**_sample_ids())
        state["guardrail_blocked"] = False
        state["unified_score"] = 0.90
        state["faithfulness"] = 0.92
        state["adversarial_pass_rate"] = 1.0

        assert route_after_evaluation(state) == "deployer"


class TestFailureBranch:
    """A genuinely low-scoring-but-faithful evaluation must reach Observer ->
    Diagnoser -> Improver, with all 3 real candidates persisted."""

    @pytest.mark.asyncio
    async def test_low_score_faithful_run_reaches_improver_with_three_candidates(
        self,
    ) -> None:
        # Deliberately: faithfulness/adversarial healthy (not a hallucination/hard-block
        # case), unified_score low, retrieval/latency/token metrics all within normal
        # range -- this is the honest "answer incomplete" scenario, not a forced branch.
        state = initial_state(**_sample_ids())
        state["guardrail_blocked"] = False
        state["unified_score"] = 0.55
        state["faithfulness"] = 0.85
        state["adversarial_pass_rate"] = 1.0
        state["retrieved_chunks"] = [
            {"chunk_id": "c1", "chunk_text": "relevant chunk one", "score": 0.78},
            {"chunk_id": "c2", "chunk_text": "relevant chunk two", "score": 0.71},
        ]
        state["token_count"] = 1200
        state["latency_p95_ms"] = 900
        state["retry_count"] = 0
        state["max_retries"] = 3
        state["quality_trend"] = "stable"

        # 1. Evaluator routing must send this into the retry loop.
        assert route_after_evaluation(state) == "observer"

        # 2. Observer: real node, no LLM, real DB query (historical runs may be empty).
        after_observer = await observer_node(state)
        assert after_observer["retry_count"] == 1
        assert "observation_flags" in after_observer

        # 3. Routing after Observer must continue to Diagnoser (retries remain).
        assert route_after_observer(after_observer) == "diagnoser"

        # 4. Diagnoser: real node, real LLM classification call (not mocked).
        after_diagnoser = await diagnoser_node(after_observer)
        assert after_diagnoser["failure_type"] in {
            "F-01",
            "F-02",
            "F-03",
            "F-04",
            "F-05",
            "F-06",
        }
        confidence = after_diagnoser["confidence"]
        assert confidence is not None
        assert 0.0 <= confidence <= 1.0
        # Faithfulness was healthy (0.85) -- the rule-based fast path only fires F-03
        # below 0.5, so this must NOT be misclassified as hallucination.
        assert after_diagnoser["failure_type"] != "F-03"

        # 5. Improver: real node (heuristic scoring + fast-failing MLflow logging,
        #    no LLM call) -- must persist all 3 scored candidates, not just the winner.
        after_improver = await improver_node(after_diagnoser)
        candidates = after_improver["improver_candidates"]
        assert len(candidates) == 3
        winners = [c for c in candidates if c["is_winner"]]
        assert len(winners) == 1
        assert after_improver["variant_id"] == winners[0]["variant_id"]
        assert after_improver["variant_config"] == winners[0]["config"]
        assert after_improver["improvement_attempt"] == 1
