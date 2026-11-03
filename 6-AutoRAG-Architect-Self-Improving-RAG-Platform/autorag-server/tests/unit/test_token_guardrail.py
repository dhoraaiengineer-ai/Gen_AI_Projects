"""Unit tests for TokenGuardrail service.

Task E-17: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Rule 80: all critical guardrail paths must have tests.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.token_guardrail import (
    TokenBudgetType,
    TokenCheckResult,
    TokenGuardrail,
)


@pytest.fixture
def guardrail() -> TokenGuardrail:
    return TokenGuardrail()


class TestTokenGuardrailAllowed:
    def test_tokens_within_prompt_limit_is_allowed(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=32000):
            result = guardrail.check(5000, TokenBudgetType.PROMPT, "trace-1")
        assert result.allowed is True

    def test_tokens_at_exact_limit_is_allowed(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=32000):
            result = guardrail.check(32000, TokenBudgetType.PROMPT, "trace-2")
        assert result.allowed is True

    def test_tokens_within_context_limit_is_allowed(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=64000):
            result = guardrail.check(32000, TokenBudgetType.CONTEXT, "trace-3")
        assert result.allowed is True

    def test_tokens_within_completion_limit_is_allowed(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=4096):
            result = guardrail.check(512, TokenBudgetType.COMPLETION, "trace-4")
        assert result.allowed is True


class TestTokenGuardrailBlocked:
    def test_tokens_above_prompt_limit_is_blocked(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=32000):
            result = guardrail.check(50000, TokenBudgetType.PROMPT, "trace-5")
        assert result.allowed is False

    def test_blocked_result_has_reason(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=4096):
            result = guardrail.check(8000, TokenBudgetType.COMPLETION, "trace-6")
        assert "exceeds" in result.reason
        assert "limit" in result.reason

    def test_blocked_result_carries_correct_budget_type(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=64000):
            result = guardrail.check(70000, TokenBudgetType.CONTEXT, "trace-7")
        assert result.budget_type == TokenBudgetType.CONTEXT

    def test_blocked_result_carries_correct_amounts(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=32000):
            result = guardrail.check(40000, TokenBudgetType.PROMPT, "trace-8")
        assert result.requested_tokens == 40000
        assert result.budget_limit == 32000


class TestTokenGuardrailReturnType:
    def test_returns_token_check_result(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=32000):
            result = guardrail.check(1000, TokenBudgetType.PROMPT, "trace-9")
        assert isinstance(result, TokenCheckResult)

    def test_allowed_result_has_within_budget_reason(self, guardrail: TokenGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=32000):
            result = guardrail.check(1000, TokenBudgetType.PROMPT, "trace-10")
        assert "budget" in result.reason
