"""Token budgets (ADR-029): estimation, trimming, line fitting, per-request meter."""

from __future__ import annotations

import pytest

from src.core.tokens import (
    BudgetExceeded,
    current_meter,
    estimate_tokens,
    fit_lines,
    start_meter,
    stop_meter,
    trim_to_tokens,
)


def test_estimate_and_trim() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd" * 10) == 10
    trimmed = trim_to_tokens("x" * 1000, 50)
    assert len(trimmed) <= 200 and trimmed.endswith("[trimmed]")
    assert trim_to_tokens("short", 50) == "short"


def test_fit_lines_keeps_whole_lines_in_order() -> None:
    lines = ["a" * 40, "b" * 40, "c" * 40]  # 10 tokens each (+1 separator)
    assert fit_lines(lines, 23) == lines[:2]
    assert fit_lines(lines, 5) == []


def test_meter_enforces_request_budget_and_summarises() -> None:
    meter, token = start_meter(1_000)
    try:
        assert current_meter() is meter
        meter.record("euri:gpt-4.1-mini", 600, 150, 0.0005)
        meter.ensure_available()
        meter.record("groq:qwen", 200, 60, 0.0001)
        with pytest.raises(BudgetExceeded) as info:
            meter.ensure_available()
        assert info.value.status_code == 429
        summary = meter.summary()
        assert summary["llmCalls"] == 2 and summary["tokensTotal"] == 1_010
        assert summary["models"] == ["euri:gpt-4.1-mini", "groq:qwen"]
    finally:
        stop_meter(token)
    assert current_meter() is None
