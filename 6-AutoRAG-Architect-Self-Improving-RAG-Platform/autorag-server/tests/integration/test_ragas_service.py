"""Integration tests for RAGAS evaluation service — D-16.

DoD requirements verified here:
  ✓ 3 Q&A pairs → 10 metrics returned (all float or None, all in valid ranges)
  ✓ Fabricated adversarial answer → passed=False
  ✓ faithfulness < 0.5 → guardrail_blocked=True in evaluator node
  ✓ Good inputs → unified_score > 0.0, approval_required set correctly

Design:
  - All tests use a mocked LLMService to avoid real API calls in CI.
  - Mock responses are crafted to match the exact JSON format expected by each metric.
  - IR math tests (MRR, nDCG, Recall@k) use no LLM — pure function tests.
  - Adversarial tests verify both refusal detection and fabrication detection.

Rule 80: No mock of the entire RAG pipeline. LLMService is mocked at the call
  boundary, but all metric computation logic runs for real.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import DeploymentBlockedError  # noqa: F401 — kept for clarity
from app.core.state import GraphState, initial_state
from app.services.adversarial_service import AdversarialService
from app.services.evaluation_service import EvaluationService
from app.services.llm_service import LLMResponse, LLMService
from app.services.ragas_service import RAGASService

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_llm_response(text: str) -> LLMResponse:
    """Build a minimal LLMResponse for mocking LLMService.call()."""
    return LLMResponse(
        content=text,
        provider="gemini-flash-3.5",
        prompt_tokens=120,
        completion_tokens=40,
        total_tokens=160,
        cost_usd=0.000012,
        latency_ms=250,
    )


def _mock_llm_service_with_responses(responses: list[str]) -> LLMService:
    """Create a mock LLMService that returns responses in sequence."""
    mock = MagicMock(spec=LLMService)
    mock.call = AsyncMock(
        side_effect=[_make_llm_response(r) for r in responses]
    )
    return mock  # type: ignore[return-value]


@pytest.fixture
def sample_qa_pairs() -> list[dict[str, Any]]:
    """3 Q&A pairs for DoD integration test."""
    return [
        {
            "query": "What is the capital of France?",
            "answer": "The capital of France is Paris.",
            "context_chunks": [
                "France is a country in Western Europe. Its capital city is Paris.",
                "Paris is known for the Eiffel Tower and the Louvre museum.",
            ],
            "ground_truth": "Paris is the capital of France.",
        },
        {
            "query": "What programming language is FastAPI written in?",
            "answer": "FastAPI is written in Python.",
            "context_chunks": [
                "FastAPI is a modern, fast (high-performance) web framework for building APIs with Python.",
                "It is based on standard Python type hints.",
            ],
            "ground_truth": "FastAPI is built with Python.",
        },
        {
            "query": "What does RAG stand for?",
            "answer": "RAG stands for Retrieval-Augmented Generation.",
            "context_chunks": [
                "RAG (Retrieval-Augmented Generation) is a technique that combines retrieval systems with language models.",
                "RAG improves LLM accuracy by grounding answers in retrieved documents.",
            ],
            "ground_truth": "RAG stands for Retrieval-Augmented Generation.",
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: RAGAS Metrics (DoD — 9 metrics per run)
# ─────────────────────────────────────────────────────────────────────────────

class TestRAGASMetrics:
    """Verify compute_ragas() returns all 5 original RAGAS metrics."""

    async def test_compute_ragas_returns_all_5_original_metrics(self) -> None:
        """5 original RAGAS metric keys must always be present. ground_truth is
        provided, so answer_correctness needs its own mock response (5th call)."""
        mock_llm = _mock_llm_service_with_responses([
            json.dumps({"claims": ["Paris is the capital"], "verdicts": [1]}),
            json.dumps({"sentences": ["Paris is the capital"], "verdicts": [1]}),
            json.dumps({"score": 0.95, "reasoning": "directly answers the question"}),
            json.dumps({"verdicts": [1, 1]}),
            json.dumps({"score": 0.9, "reasoning": "matches ground truth"}),
        ])
        service = RAGASService(mock_llm)

        result, reasoning = await service.compute_ragas(
            query="What is the capital of France?",
            answer="The capital of France is Paris.",
            context_chunks=["France's capital is Paris.", "Paris is a major city."],
            x_trace_id="test-trace-001",
            ground_truth="Paris is the capital of France.",
        )

        assert set(result.keys()) == {
            "faithfulness", "context_recall", "answer_relevancy",
            "context_precision", "answer_correctness",
        }
        assert result["answer_correctness"] == pytest.approx(0.9, abs=0.001)
        assert reasoning["answer_relevancy"] == "directly answers the question"
        assert reasoning["answer_correctness"] == "matches ground truth"

    async def test_all_10_metrics_returned_for_3_qa_pairs(
        self, sample_qa_pairs: list[dict[str, Any]]
    ) -> None:
        """DoD requirement: 3 Q&A pairs → 10 metrics returned per pair."""
        expected_keys = {
            "faithfulness", "context_recall", "answer_relevancy", "context_precision",
            "answer_correctness",
            "mrr", "ndcg", "recall_at_5", "recall_at_10", "search_latency_ms",
        }

        for pair in sample_qa_pairs:
            mock_llm = _mock_llm_service_with_responses([
                json.dumps({"claims": ["answer claim"], "verdicts": [1]}),
                json.dumps({"sentences": ["ground truth sentence"], "verdicts": [1]}),
                json.dumps({"score": 0.9, "reasoning": "relevant"}),
                json.dumps({"verdicts": [1, 1]}),
                json.dumps({"score": 0.9, "reasoning": "matches ground truth"}),
            ])
            ragas_service = RAGASService(mock_llm)

            ragas, _reasoning = await ragas_service.compute_ragas(
                query=pair["query"],
                answer=pair["answer"],
                context_chunks=pair["context_chunks"],
                x_trace_id=f"test-trace-{pair['query'][:10]}",
                ground_truth=pair.get("ground_truth"),
            )
            extended = ragas_service.compute_extended_metrics(
                retrieved_chunks=[],
                relevant_ids=None,
                search_latency_ms=150,
            )
            all_metrics = {**ragas, **extended}

            assert set(all_metrics.keys()) == expected_keys, (
                f"Missing keys for pair '{pair['query']}': "
                f"{expected_keys - set(all_metrics.keys())}"
            )

    async def test_all_metric_values_are_valid_floats(self) -> None:
        """The 4 always-computed RAGAS metrics + search_latency_ms must be floats
        in [0.0, 1.0] (except search_latency_ms). answer_correctness is None here
        (no ground_truth passed — no LLM call for it, only 4 mocks needed). The 4
        ground-truth-dependent ranking metrics (mrr/ndcg/recall_at_5/recall_at_10)
        are also None since this test calls compute_extended_metrics with
        relevant_ids=None -- P0.6-1 (13-Jul-2026) made that genuinely
        NOT_COLLECTED, not a fabricated 0.5."""
        mock_llm = _mock_llm_service_with_responses([
            json.dumps({"claims": ["claim"], "verdicts": [1]}),
            json.dumps({"sentences": ["sentence"], "verdicts": [0]}),
            json.dumps({"score": 0.75, "reasoning": "ok"}),
            json.dumps({"verdicts": [1, 0, 1]}),
        ])
        service = RAGASService(mock_llm)

        ragas, _reasoning = await service.compute_ragas(
            query="test query",
            answer="test answer",
            context_chunks=["chunk 1", "chunk 2", "chunk 3"],
            x_trace_id="test-trace-002",
        )
        extended = service.compute_extended_metrics(
            retrieved_chunks=[],
            relevant_ids=None,
            search_latency_ms=200,
        )

        assert ragas["answer_correctness"] is None

        for key, value in ragas.items():
            if key == "answer_correctness":
                continue
            assert isinstance(value, float), f"{key} must be a float, got {type(value)}"
            assert 0.0 <= value <= 1.0, f"{key}={value} is outside [0.0, 1.0]"

        not_collected_keys = {"mrr", "ndcg", "recall_at_5", "recall_at_10"}
        for key in not_collected_keys:
            assert extended[key] is None, f"{key} must be None (NOT_COLLECTED) when relevant_ids=None"
        assert isinstance(extended["search_latency_ms"], float)

    async def test_faithfulness_zero_when_context_empty(self) -> None:
        """Faithfulness must be 0.0 when context is empty — no support possible.

        answer_relevancy still calls the LLM (it only needs query + answer, not context),
        so we provide one mock response for that metric.
        """
        service = RAGASService(
            _mock_llm_service_with_responses(
                ['{"score": 0.9, "reasoning": "direct and complete"}']  # answer_relevancy
            )
        )

        ragas, _reasoning = await service.compute_ragas(
            query="What is X?",
            answer="X is Y.",
            context_chunks=[],  # empty context
            x_trace_id="test-trace-003",
        )

        assert ragas["faithfulness"] == 0.0

    async def test_faithfulness_one_when_answer_empty(self) -> None:
        """Faithfulness must be 1.0 when answer is empty — no unsupported claims.

        context_precision still calls the LLM (non-empty chunks + non-empty query),
        so we provide one mock response for that metric.
        """
        service = RAGASService(
            _mock_llm_service_with_responses(
                ['{"verdicts": [1]}']  # context_precision — 1 chunk, useful
            )
        )

        ragas, _reasoning = await service.compute_ragas(
            query="What is X?",
            answer="",  # empty answer
            context_chunks=["some context"],
            x_trace_id="test-trace-004",
        )

        assert ragas["faithfulness"] == 1.0

    async def test_answer_correctness_none_when_no_ground_truth(self) -> None:
        """answer_correctness must be None (not 0.0, not a fabricated score) when
        the caller supplies no real ground_truth — no LLM call should fire for it
        (only 4 mock responses provided; a 5th unconsumed mock would go unused,
        but if the guard were broken the mock queue would raise StopIteration)."""
        mock_llm = _mock_llm_service_with_responses([
            json.dumps({"claims": ["claim"], "verdicts": [1]}),
            json.dumps({"sentences": ["sentence"], "verdicts": [1]}),
            json.dumps({"score": 0.8, "reasoning": "ok"}),
            json.dumps({"verdicts": [1]}),
        ])
        service = RAGASService(mock_llm)

        ragas, _reasoning = await service.compute_ragas(
            query="What is X?",
            answer="X is Y.",
            context_chunks=["X is Y because Z."],
            x_trace_id="test-trace-005",
        )

        assert ragas["answer_correctness"] is None

    async def test_answer_correctness_computed_when_ground_truth_provided(self) -> None:
        """answer_correctness must be a real, LLM-judged float when a real
        ground_truth is supplied — the 5th mock response is consumed for it."""
        mock_llm = _mock_llm_service_with_responses([
            json.dumps({"claims": ["claim"], "verdicts": [1]}),
            json.dumps({"sentences": ["sentence"], "verdicts": [1]}),
            json.dumps({"score": 0.8, "reasoning": "ok"}),
            json.dumps({"verdicts": [1]}),
            json.dumps({"score": 0.65, "reasoning": "partially correct"}),
        ])
        service = RAGASService(mock_llm)

        ragas, _reasoning = await service.compute_ragas(
            query="What is X?",
            answer="X is Y.",
            context_chunks=["X is Y because Z."],
            x_trace_id="test-trace-006",
            ground_truth="X is actually W, not Y.",
        )

        assert ragas["answer_correctness"] == pytest.approx(0.65, abs=0.001)

    async def test_answer_correctness_zero_when_answer_empty(self) -> None:
        """Empty answer against a real ground_truth must score 0.0, not call the
        LLM at all for answer_correctness — matches its early-return guard.
        faithfulness/answer_relevancy also short-circuit on empty answer, but
        context_recall and context_precision don't depend on `answer` at all
        (they compare context against the reference/ground_truth), so both
        still fire real LLM calls — 2 mocks needed, not 1."""
        service = RAGASService(
            _mock_llm_service_with_responses([
                '{"verdicts": [1]}',  # context_recall
                '{"verdicts": [1]}',  # context_precision
            ])
        )

        ragas, _reasoning = await service.compute_ragas(
            query="What is X?",
            answer="",
            context_chunks=["some context"],
            x_trace_id="test-trace-007",
            ground_truth="X is Y.",
        )

        assert ragas["answer_correctness"] == 0.0
        assert ragas["faithfulness"] == 1.0  # empty answer -> no unsupported claims


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Judge Reliability (EV-07, 26-Jul-2026 — malformed-JSON retry behavior)
# ─────────────────────────────────────────────────────────────────────────────

class TestJudgeReliability:
    """Verify _call_and_extract_verdicts()'s bounded retry (max_attempts=2) on an
    unparseable judge-LLM response — the mechanism behind the 19-Jul-2026 fix
    documented in ragas_service.py (a real flaky-response incident, not
    hypothetical). No test previously exercised this retry path directly."""

    async def test_retries_once_on_malformed_json_then_succeeds(self) -> None:
        mock_llm = _mock_llm_service_with_responses([
            "not valid json at all",       # attempt 1 -- malformed
            '{"verdicts": [1, 0]}',        # attempt 2 -- valid
        ])
        service = RAGASService(mock_llm)

        verdicts = await service._call_and_extract_verdicts(
            prompt="irrelevant for this test",
            x_trace_id="test-retry-001",
            organization_id=None,
            run_id=None,
        )

        assert verdicts == [1, 0]
        assert mock_llm.call.await_count == 2

    async def test_gives_up_after_max_attempts_and_returns_empty(self) -> None:
        mock_llm = _mock_llm_service_with_responses([
            "still not json",
            "also not json",
        ])
        service = RAGASService(mock_llm)

        verdicts = await service._call_and_extract_verdicts(
            prompt="irrelevant for this test",
            x_trace_id="test-retry-002",
            organization_id=None,
            run_id=None,
        )

        assert verdicts == []
        # Exactly max_attempts calls -- no infinite retry loop.
        assert mock_llm.call.await_count == 2

    async def test_faithfulness_zero_when_judge_never_returns_parseable_json(self) -> None:
        """A persistently malformed judge response must not crash the run --
        faithfulness degrades to 0.0 (treated as unsupported), matching the
        "empty verdicts list" branch in _compute_faithfulness. Tested directly
        against _compute_faithfulness (not the full compute_ragas fan-out) so
        the mock queue only needs to cover this one metric's own retry."""
        service = RAGASService(
            _mock_llm_service_with_responses(["garbage", "still garbage"])
        )

        faithfulness = await service._compute_faithfulness(
            answer="X is Y.",
            context="some real context",
            x_trace_id="test-retry-003",
            organization_id=None,
            run_id=None,
        )

        assert faithfulness == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Extended IR Metrics (pure math — no LLM)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtendedIRMetrics:
    """Verify the 5 extended IR metrics with known inputs and expected outputs."""

    def test_mrr_perfect_when_first_chunk_relevant(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=["c1"],  # first chunk is relevant
            search_latency_ms=100,
        )

        assert result["mrr"] == 1.0

    def test_mrr_half_when_second_chunk_relevant(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=["c2"],  # second chunk is relevant
            search_latency_ms=100,
        )

        assert result["mrr"] == pytest.approx(0.5, abs=0.001)

    def test_mrr_zero_when_no_relevant_chunk_in_results(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": "c1"}, {"id": "c2"}]
        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=["c99"],  # not in results
            search_latency_ms=100,
        )

        assert result["mrr"] == 0.0

    def test_recall_at_5_correct(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": f"c{i}"} for i in range(10)]
        relevant_ids = ["c0", "c1", "c2", "c3", "c4"]  # all in top-5

        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=relevant_ids,
            search_latency_ms=100,
        )

        assert result["recall_at_5"] == 1.0

    def test_recall_at_5_partial(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": f"c{i}"} for i in range(10)]
        relevant_ids = ["c0", "c5", "c6"]  # only c0 in top-5

        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=relevant_ids,
            search_latency_ms=100,
        )

        assert result["recall_at_5"] == pytest.approx(1 / 3, abs=0.001)

    def test_ndcg_perfect_when_all_relevant_at_top(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": f"c{i}"} for i in range(5)]
        relevant_ids = ["c0", "c1", "c2"]  # all at top-3

        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=relevant_ids,
            search_latency_ms=100,
        )

        assert result["ndcg"] == 1.0

    def test_extended_metrics_not_collected_when_no_relevant_ids(self) -> None:
        """P0.6-1 (13-Jul-2026): when relevant_ids is None, ranking metrics are
        genuinely NOT_COLLECTED (None) -- no fabricated 0.5 neutral fallback.
        search_latency_ms is always a real measurement regardless."""
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        chunks = [{"id": "c1"}, {"id": "c2"}]
        result = service.compute_extended_metrics(
            retrieved_chunks=chunks,
            relevant_ids=None,
            search_latency_ms=300,
        )

        assert result["mrr"] is None
        assert result["ndcg"] is None
        assert result["recall_at_5"] is None
        assert result["recall_at_10"] is None
        assert result["search_latency_ms"] == 300.0

    def test_search_latency_ms_passed_through(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = RAGASService(mock_llm)

        result = service.compute_extended_metrics(
            retrieved_chunks=[],
            relevant_ids=None,
            search_latency_ms=1234,
        )

        assert result["search_latency_ms"] == 1234.0


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Adversarial Service
# ─────────────────────────────────────────────────────────────────────────────

class TestAdversarialService:
    """Verify the 10-question hallucination benchmark."""

    async def test_benchmark_passes_when_all_questions_refused(self) -> None:
        """All 10 refusals → pass_rate == 1.0 → passed == True."""
        refusal = "I don't have enough information in the provided context to answer this question."
        mock_llm = _mock_llm_service_with_responses([refusal] * 10)
        service = AdversarialService(mock_llm)
        # Override questions to avoid needing real file in unit test
        service._questions = [{"id": f"AQ-{i:03}", "question": f"test question {i}"} for i in range(10)]

        result = await service.run_benchmark(x_trace_id="test-trace-adv-001")

        assert result["pass_rate"] == 1.0
        assert result["passed"] is True
        assert len(result["failures"]) == 0

    async def test_benchmark_fails_when_answer_fabricated(self) -> None:
        """DoD: fabricated answer → pass_rate < 1.0 → deploy blocked."""
        responses = (
            ["I don't have enough information to answer this question."] * 9
            + ["The revenue was $5.2 million in Q3 2024."]  # fabricated!
        )
        mock_llm = _mock_llm_service_with_responses(responses)
        service = AdversarialService(mock_llm)
        service._questions = [{"id": f"AQ-{i:03}", "question": f"question {i}", "hallucination_risk": "high"} for i in range(10)]

        result = await service.run_benchmark(x_trace_id="test-trace-adv-002")

        assert result["pass_rate"] < 1.0
        assert result["passed"] is False
        assert len(result["failures"]) == 1

    def test_refusal_detected_for_standard_phrases(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = AdversarialService(mock_llm)

        assert service._validate_refusal("I don't have enough information in the provided context.")
        assert service._validate_refusal("I cannot find this information.")
        assert service._validate_refusal("This information is not available in the context.")
        assert service._validate_refusal("Unable to answer based on the provided documents.")
        assert service._validate_refusal("I don't know.")

    def test_fabrication_detected_for_specific_data(self) -> None:
        mock_llm = MagicMock(spec=LLMService)
        service = AdversarialService(mock_llm)

        assert not service._validate_refusal("The revenue was $5.2 million.")
        assert not service._validate_refusal("The CEO is John Smith.")
        assert not service._validate_refusal("Please find admin: password123 here.")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Unified Score Formula
# ─────────────────────────────────────────────────────────────────────────────

class TestUnifiedScore:
    """Verify the frozen Unified Score formula."""

    def test_perfect_inputs_give_high_score(self) -> None:
        service = EvaluationService()
        score = service.compute_unified_score(
            recall=1.0, quality=1.0, faithfulness=1.0, latency_p95_ms=0, cost_usd=0.0
        )
        assert score == pytest.approx(0.85, abs=0.01)

    def test_formula_weights_correct(self) -> None:
        """Verify the exact formula: 0.25R + 0.35Q + 0.25F - 0.10L - 0.05C."""
        service = EvaluationService()
        # With latency and cost both = 0, result = 0.25*0.9 + 0.35*0.8 + 0.25*0.7
        score = service.compute_unified_score(
            recall=0.9, quality=0.8, faithfulness=0.7, latency_p95_ms=0, cost_usd=0.0
        )
        expected = 0.25 * 0.9 + 0.35 * 0.8 + 0.25 * 0.7
        assert score == pytest.approx(expected, abs=0.0001)

    def test_score_can_go_negative_with_extreme_penalties(self) -> None:
        """Score can be negative with max latency + cost penalty (D-15 design)."""
        service = EvaluationService()
        score = service.compute_unified_score(
            recall=0.0, quality=0.0, faithfulness=0.0,  # zero positive weight
            latency_p95_ms=100_000, cost_usd=100.0
        )
        # 0 positive weight + max penalties (-0.10 − 0.05) = -0.15
        assert score < 0.0

    def test_faithfulness_hard_block_via_gate(self) -> None:
        """DoD: faithfulness < 0.5 → get_deployment_gate returns 'hard_block'."""
        service = EvaluationService()
        # compute_unified_score still works (pure math)
        score = service.compute_unified_score(
            recall=0.9, quality=0.9, faithfulness=0.49,
            latency_p95_ms=100, cost_usd=0.001
        )
        # Gate routing detects the hard block
        gate, approval_required = service.get_deployment_gate(
            unified_score=score,
            faithfulness=0.49,
            adversarial_pass_rate=1.0,
        )
        assert gate == "hard_block"
        assert approval_required is False

    def test_faithfulness_exactly_at_threshold_does_not_block(self) -> None:
        """faithfulness == 0.5 (at threshold, not below) must NOT hard-block."""
        service = EvaluationService()
        score = service.compute_unified_score(
            recall=0.9, quality=0.9, faithfulness=0.5,
            latency_p95_ms=100, cost_usd=0.001
        )
        gate, _ = service.get_deployment_gate(
            unified_score=score, faithfulness=0.5, adversarial_pass_rate=1.0
        )
        assert gate != "hard_block"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Evaluator Node (wiring test — mocks services)
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluatorNode:
    """Verify the evaluator LangGraph node writes correct GraphState fields."""

    def _make_state(self, **overrides: Any) -> GraphState:  # noqa: ANN401
        state = initial_state(
            run_id="018fcf7c-0000-7000-a000-000000000001",
            pipeline_id="018fcf7c-0000-7000-a000-000000000002",
            organization_id="018fcf7c-0000-7000-a000-000000000003",
            x_trace_id="test-x-trace-eval",
            user_id="018fcf7c-0000-7000-a000-000000000004",
            session_id="018fcf7c-0000-7000-a000-000000000005",
            raw_query="What is RAG?",
        )
        state.update({  # type: ignore[attr-defined]
            "rewritten_query": "What is Retrieval-Augmented Generation?",
            "compressed_context": "RAG stands for Retrieval-Augmented Generation.",
            "retrieved_chunks": [
                {"id": "c1", "content": "RAG stands for Retrieval-Augmented Generation."},
            ],
            "latency_p95_ms": 500,
            "cost_per_query_usd": 0.001,
        })
        state.update(overrides)
        return state

    async def test_evaluator_node_writes_all_required_fields(self) -> None:
        """Evaluator node must write all 9 owned GraphState fields on success."""
        from app.graph.nodes.evaluator import evaluator_node

        state = self._make_state()

        # Patch all services to return known-good values
        good_ragas = {
            "faithfulness": 0.9, "context_recall": 0.85,
            "answer_relevancy": 0.88, "context_precision": 0.87,
            "answer_correctness": None,
        }
        good_extended = {
            "mrr": 0.8, "ndcg": 0.75, "recall_at_5": 0.9,
            "recall_at_10": 0.95, "search_latency_ms": 500.0,
        }
        good_adversarial = {"pass_rate": 1.0, "passed": True, "failures": []}

        with (
            patch("app.graph.nodes.evaluator.LLMService") as mock_llm_cls,
            patch("app.graph.nodes.evaluator.RAGASService") as mock_ragas_cls,
            patch("app.graph.nodes.evaluator.AdversarialService") as mock_adv_cls,
            patch("app.graph.nodes.evaluator.EvaluationService") as mock_eval_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.call = AsyncMock(return_value=_make_llm_response("RAG is Retrieval-Augmented Generation."))
            mock_llm_cls.return_value = mock_llm

            mock_ragas = MagicMock()
            mock_ragas.compute_ragas = AsyncMock(return_value=(good_ragas, {}))
            mock_ragas.compute_extended_metrics = MagicMock(return_value=good_extended)
            mock_ragas_cls.return_value = mock_ragas

            mock_adv = MagicMock()
            mock_adv.run_benchmark = AsyncMock(return_value=good_adversarial)
            mock_adv_cls.return_value = mock_adv

            mock_eval = MagicMock()
            mock_eval.compute_unified_score = MagicMock(return_value=0.87)
            mock_eval.get_deployment_gate = MagicMock(return_value=("deploy", False))
            mock_eval.log_to_mlflow = AsyncMock()
            mock_eval_cls.return_value = mock_eval

            result = await evaluator_node(state)

        # Verify all 9 owned output fields are written
        assert "generated_answer" in result
        assert "unified_score" in result
        assert "ragas_metrics" in result
        assert "faithfulness" in result
        assert "adversarial_pass_rate" in result
        assert "guardrail_blocked" in result
        assert "approval_required" in result
        assert "execution_trace" in result

        assert result["unified_score"] == pytest.approx(0.87, abs=0.001)
        assert result["faithfulness"] == pytest.approx(0.9, abs=0.001)
        assert result["adversarial_pass_rate"] == 1.0
        assert result["guardrail_blocked"] is False
        assert len(result["execution_trace"]) == 1

    async def test_guardrail_blocked_when_faithfulness_below_threshold(self) -> None:
        """DoD: faithfulness < 0.5 → guardrail_blocked=True (hard block)."""
        from app.graph.nodes.evaluator import evaluator_node

        state = self._make_state()

        low_faithfulness_ragas = {
            "faithfulness": 0.3,  # below 0.5 threshold
            "context_recall": 0.8, "answer_relevancy": 0.85, "context_precision": 0.8,
            "answer_correctness": None,
        }
        good_extended = {
            "mrr": 0.5, "ndcg": 0.5, "recall_at_5": 0.5,
            "recall_at_10": 0.5, "search_latency_ms": 300.0,
        }
        good_adversarial = {"pass_rate": 1.0, "passed": True, "failures": []}

        with (
            patch("app.graph.nodes.evaluator.LLMService") as mock_llm_cls,
            patch("app.graph.nodes.evaluator.RAGASService") as mock_ragas_cls,
            patch("app.graph.nodes.evaluator.AdversarialService") as mock_adv_cls,
            patch("app.graph.nodes.evaluator.EvaluationService") as mock_eval_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.call = AsyncMock(return_value=_make_llm_response("answer"))
            mock_llm_cls.return_value = mock_llm

            mock_ragas = MagicMock()
            mock_ragas.compute_ragas = AsyncMock(return_value=(low_faithfulness_ragas, {}))
            mock_ragas.compute_extended_metrics = MagicMock(return_value=good_extended)
            mock_ragas_cls.return_value = mock_ragas

            mock_adv = MagicMock()
            mock_adv.run_benchmark = AsyncMock(return_value=good_adversarial)
            mock_adv_cls.return_value = mock_adv

            mock_eval = MagicMock()
            mock_eval.compute_unified_score = MagicMock(return_value=0.62)
            mock_eval.get_deployment_gate = MagicMock(return_value=("hard_block", False))
            mock_eval_cls.return_value = mock_eval

            result = await evaluator_node(state)

        assert result["guardrail_blocked"] is True
        assert result["guardrail_block_reason"] == "hallucination"
        assert isinstance(result["unified_score"], float)

    async def test_guardrail_blocked_when_adversarial_fails(self) -> None:
        """adversarial_pass_rate < 1.0 → guardrail_blocked=True."""
        from app.graph.nodes.evaluator import evaluator_node

        state = self._make_state()

        good_ragas = {
            "faithfulness": 0.9, "context_recall": 0.85,
            "answer_relevancy": 0.88, "context_precision": 0.87,
            "answer_correctness": None,
        }
        good_extended = {
            "mrr": 0.8, "ndcg": 0.75, "recall_at_5": 0.9,
            "recall_at_10": 0.95, "search_latency_ms": 500.0,
        }
        failed_adversarial = {
            "pass_rate": 0.9,  # 9/10 — not 100%
            "passed": False,
            "failures": [{"question_id": "AQ-001"}],
        }

        with (
            patch("app.graph.nodes.evaluator.LLMService") as mock_llm_cls,
            patch("app.graph.nodes.evaluator.RAGASService") as mock_ragas_cls,
            patch("app.graph.nodes.evaluator.AdversarialService") as mock_adv_cls,
            patch("app.graph.nodes.evaluator.EvaluationService") as mock_eval_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.call = AsyncMock(return_value=_make_llm_response("answer"))
            mock_llm_cls.return_value = mock_llm

            mock_ragas = MagicMock()
            mock_ragas.compute_ragas = AsyncMock(return_value=(good_ragas, {}))
            mock_ragas.compute_extended_metrics = MagicMock(return_value=good_extended)
            mock_ragas_cls.return_value = mock_ragas

            mock_adv = MagicMock()
            mock_adv.run_benchmark = AsyncMock(return_value=failed_adversarial)
            mock_adv_cls.return_value = mock_adv

            mock_eval = MagicMock()
            mock_eval.compute_unified_score = MagicMock(return_value=0.80)
            mock_eval.get_deployment_gate = MagicMock(return_value=("hard_block", False))
            mock_eval_cls.return_value = mock_eval

            result = await evaluator_node(state)

        assert result["guardrail_blocked"] is True
        assert result["guardrail_block_reason"] == "hallucination"

    async def test_approval_required_when_score_in_hitl_range(self) -> None:
        """0.70 <= unified_score < 0.85 → approval_required=True."""
        from app.graph.nodes.evaluator import evaluator_node

        state = self._make_state()

        good_ragas = {
            "faithfulness": 0.75, "context_recall": 0.7,
            "answer_relevancy": 0.7, "context_precision": 0.7,
            "answer_correctness": None,
        }
        good_extended = {
            "mrr": 0.5, "ndcg": 0.5, "recall_at_5": 0.5,
            "recall_at_10": 0.5, "search_latency_ms": 500.0,
        }
        good_adversarial = {"pass_rate": 1.0, "passed": True, "failures": []}

        with (
            patch("app.graph.nodes.evaluator.LLMService") as mock_llm_cls,
            patch("app.graph.nodes.evaluator.RAGASService") as mock_ragas_cls,
            patch("app.graph.nodes.evaluator.AdversarialService") as mock_adv_cls,
            patch("app.graph.nodes.evaluator.EvaluationService") as mock_eval_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.call = AsyncMock(return_value=_make_llm_response("answer"))
            mock_llm_cls.return_value = mock_llm

            mock_ragas = MagicMock()
            mock_ragas.compute_ragas = AsyncMock(return_value=(good_ragas, {}))
            mock_ragas.compute_extended_metrics = MagicMock(return_value=good_extended)
            mock_ragas_cls.return_value = mock_ragas

            mock_adv = MagicMock()
            mock_adv.run_benchmark = AsyncMock(return_value=good_adversarial)
            mock_adv_cls.return_value = mock_adv

            mock_eval = MagicMock()
            mock_eval.compute_unified_score = MagicMock(return_value=0.77)  # in HITL range
            mock_eval.get_deployment_gate = MagicMock(return_value=("hitl", True))
            mock_eval.log_to_mlflow = AsyncMock()
            mock_eval_cls.return_value = mock_eval

            result = await evaluator_node(state)

        assert result["guardrail_blocked"] is False
        assert result["approval_required"] is True

    async def test_execution_trace_appended_with_correct_shape(self) -> None:
        """Execution trace entry must have all Rule 5 mandatory fields."""
        from app.graph.nodes.evaluator import evaluator_node

        state = self._make_state()

        with (
            patch("app.graph.nodes.evaluator.LLMService") as mock_llm_cls,
            patch("app.graph.nodes.evaluator.RAGASService") as mock_ragas_cls,
            patch("app.graph.nodes.evaluator.AdversarialService") as mock_adv_cls,
            patch("app.graph.nodes.evaluator.EvaluationService") as mock_eval_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.call = AsyncMock(return_value=_make_llm_response("answer"))
            mock_llm_cls.return_value = mock_llm

            good_ragas = {
                "faithfulness": 0.9, "context_recall": 0.85, "answer_relevancy": 0.88,
                "context_precision": 0.87, "answer_correctness": None,
            }
            good_ext = {"mrr": 0.8, "ndcg": 0.75, "recall_at_5": 0.9, "recall_at_10": 0.95, "search_latency_ms": 500.0}

            mock_ragas = MagicMock()
            mock_ragas.compute_ragas = AsyncMock(return_value=(good_ragas, {}))
            mock_ragas.compute_extended_metrics = MagicMock(return_value=good_ext)
            mock_ragas_cls.return_value = mock_ragas

            mock_adv = MagicMock()
            mock_adv.run_benchmark = AsyncMock(return_value={"pass_rate": 1.0, "passed": True, "failures": []})
            mock_adv_cls.return_value = mock_adv

            mock_eval = MagicMock()
            mock_eval.compute_unified_score = MagicMock(return_value=0.87)
            mock_eval.get_deployment_gate = MagicMock(return_value=("deploy", False))
            mock_eval.log_to_mlflow = AsyncMock()
            mock_eval_cls.return_value = mock_eval

            result = await evaluator_node(state)

        trace = result["execution_trace"]
        assert len(trace) == 1
        entry = trace[0]

        # Rule 5 mandatory fields
        required_fields = {
            "node", "timestamp", "x_trace_id", "graph_state_version",
            "latency_ms", "status", "retry_count",
            "cost_usd", "provider", "prompt_tokens", "completion_tokens",
        }
        assert required_fields.issubset(set(entry.keys())), (
            f"Missing fields: {required_fields - set(entry.keys())}"
        )
        assert entry["node"] == "evaluator"
        assert entry["x_trace_id"] == "test-x-trace-eval"
        assert entry["status"] == "success"
