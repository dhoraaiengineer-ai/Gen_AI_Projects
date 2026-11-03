"""Unit tests for AdversarialService — D-17 Adversarial Q&A Benchmark.

Test coverage:
  - _validate_refusal(): classifies refusals vs fabrications correctly
  - run_benchmark() refusal pipeline: all 10 refused → pass_rate == 1.0 → passed=True
  - run_benchmark() fabrication pipeline: model fabricates → passed=False
  - pass_rate exactness: 0.9 (9/10) is not sufficient — must be exactly 1.0
  - Dataset loading: missing file → EvaluationFailedError on run_benchmark
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.adversarial_service as adversarial_module
from app.core.exceptions import EvaluationFailedError
from app.services.adversarial_service import AdversarialService
from app.services.llm_service import LLMResponse

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_REFUSAL_TEXT = (
    "I don't have enough information in the provided context to answer this question."
)
_FABRICATION_TEXT = (
    "The CEO is John Smith and the company generated $5,200,000 in Q3 2024."
)

_TEN_QUESTIONS = [
    {
        "id": f"AQ-{i:03d}",
        "question": f"Unanswerable question {i}?",
        "hallucination_risk": "high",
        "expected_behavior": "Refuse to answer",
    }
    for i in range(1, 11)
]


def _llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        content=text,
        provider="gemini-flash-3.5",
        prompt_tokens=50,
        completion_tokens=20,
        total_tokens=70,
        cost_usd=0.0001,
        latency_ms=200,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()


@pytest.fixture
def dataset_file(tmp_path: Path) -> Path:
    """Write a 10-question adversarial dataset to a temp file and return its path."""
    path = tmp_path / "adversarial-qa.json"
    path.write_text(
        json.dumps({"_meta": {"version": "test"}, "questions": _TEN_QUESTIONS}),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def service(mock_llm: MagicMock, dataset_file: Path) -> AdversarialService:
    """AdversarialService backed by a temp dataset file and a shared mock LLM.

    Both the fixture and the test function that requests `mock_llm` receive the
    same MagicMock instance — so setting `mock_llm.call` in the test controls
    what the service calls during run_benchmark().
    """
    with patch.object(adversarial_module, "_ADVERSARIAL_DATASET_PATH", dataset_file):
        return AdversarialService(llm_service=mock_llm)


# ─────────────────────────────────────────────────────────────────────────────
# Class 1: _validate_refusal() — refusal vs fabrication classifier
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateRefusal:
    """Tests for the internal _validate_refusal() method."""

    @pytest.fixture
    def svc(self, mock_llm: MagicMock, dataset_file: Path) -> AdversarialService:
        with patch.object(adversarial_module, "_ADVERSARIAL_DATASET_PATH", dataset_file):
            return AdversarialService(llm_service=mock_llm)

    def test_standard_refusal_phrase_is_accepted(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal(_REFUSAL_TEXT) is True

    def test_cannot_find_phrase_is_accepted(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal("I cannot find this in the provided context.") is True

    def test_not_available_phrase_is_accepted(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal("This information is not available in the context.") is True

    def test_i_dont_know_is_accepted(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal("I don't know.") is True

    def test_dollar_amount_triggers_fabrication_rejection(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal("Revenue was $5,200,000 last quarter.") is False

    def test_named_ceo_triggers_fabrication_rejection(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal("The CEO is John Smith.") is False

    def test_credential_pattern_triggers_fabrication_rejection(self, svc: AdversarialService) -> None:
        assert svc._validate_refusal("admin: user123 password: secret456") is False


# ─────────────────────────────────────────────────────────────────────────────
# Class 2: refusal pipeline — pass_rate == 1.0, passed=True
# ─────────────────────────────────────────────────────────────────────────────


class TestRefusalPipeline:
    """Integration test: correctly refusing all unanswerable questions → passed=True."""

    async def test_all_refused_pass_rate_is_exactly_1(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        mock_llm.call = AsyncMock(return_value=_llm_response(_REFUSAL_TEXT))

        result = await service.run_benchmark(x_trace_id="trace-refusal-full")

        assert result["pass_rate"] == 1.0
        assert result["passed"] is True
        assert result["total_questions"] == 10
        assert result["failures"] == []

    async def test_all_refused_passed_count_is_10(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        mock_llm.call = AsyncMock(return_value=_llm_response(_REFUSAL_TEXT))

        result = await service.run_benchmark(x_trace_id="trace-refusal-count")

        assert result["passed_count"] == 10


# ─────────────────────────────────────────────────────────────────────────────
# Class 3: fabrication pipeline — passed=False, hard block triggered
# ─────────────────────────────────────────────────────────────────────────────


class TestFabricationPipeline:
    """Integration test: fabricating answer → passed=False → deployment hard blocked."""

    async def test_fabrication_on_all_questions_passed_is_false(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        """Model fabricates on every question → passed=False."""
        mock_llm.call = AsyncMock(return_value=_llm_response(_FABRICATION_TEXT))

        result = await service.run_benchmark(x_trace_id="trace-fabricate-all")

        assert result["passed"] is False

    async def test_fabrication_pass_rate_is_below_1(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        mock_llm.call = AsyncMock(return_value=_llm_response(_FABRICATION_TEXT))

        result = await service.run_benchmark(x_trace_id="trace-fabricate-rate")

        assert result["pass_rate"] < 1.0

    async def test_fabrication_failures_list_is_populated(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        mock_llm.call = AsyncMock(return_value=_llm_response(_FABRICATION_TEXT))

        result = await service.run_benchmark(x_trace_id="trace-fabricate-list")

        assert len(result["failures"]) > 0
        assert "question_id" in result["failures"][0]

    async def test_single_fabrication_among_refusals_blocks_deployment(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        """9 correct refusals + 1 fabrication → pass_rate=0.9 → still blocked."""
        responses = [_llm_response(_REFUSAL_TEXT)] * 9 + [_llm_response(_FABRICATION_TEXT)]
        mock_llm.call = AsyncMock(side_effect=responses)

        result = await service.run_benchmark(x_trace_id="trace-partial-fail")

        assert result["pass_rate"] == pytest.approx(0.9)
        assert result["passed"] is False
        assert len(result["failures"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Class 4: pass_rate exactness — only 1.0 is acceptable
# ─────────────────────────────────────────────────────────────────────────────


class TestPassRateExactness:
    """Guard: pass_rate must be exactly 1.0 — not >= 0.9, not >= 0.95."""

    async def test_09_pass_rate_is_not_sufficient(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        """9/10 refusals → 0.9 — not 1.0 — deployment must be blocked."""
        responses = [_llm_response(_REFUSAL_TEXT)] * 9 + [_llm_response(_FABRICATION_TEXT)]
        mock_llm.call = AsyncMock(side_effect=responses)

        result = await service.run_benchmark(x_trace_id="trace-exactness-09")

        assert result["pass_rate"] != 1.0
        assert result["passed"] is False

    async def test_pass_rate_1_uses_exact_float_equality(
        self, service: AdversarialService, mock_llm: MagicMock
    ) -> None:
        """10/10 refusals → pass_rate equals float 1.0 exactly (not just ≥ 1.0)."""
        mock_llm.call = AsyncMock(return_value=_llm_response(_REFUSAL_TEXT))

        result = await service.run_benchmark(x_trace_id="trace-exactness-1")

        assert result["pass_rate"] == 1.0  # exact == check, not >=


# ─────────────────────────────────────────────────────────────────────────────
# Class 5: dataset loading — missing file raises EvaluationFailedError
# ─────────────────────────────────────────────────────────────────────────────


class TestDatasetLoading:
    """Tests for graceful handling of missing dataset files."""

    async def test_missing_dataset_raises_evaluation_failed_error(
        self, mock_llm: MagicMock, tmp_path: Path
    ) -> None:
        """When dataset file does not exist, run_benchmark raises EvaluationFailedError."""
        nonexistent = tmp_path / "nonexistent.json"
        with patch.object(adversarial_module, "_ADVERSARIAL_DATASET_PATH", nonexistent):
            svc = AdversarialService(llm_service=mock_llm)

        with pytest.raises(EvaluationFailedError):
            await svc.run_benchmark(x_trace_id="trace-missing-dataset")
