"""Unit tests for CostGuardrail service.

Task E-16: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Rule 80: all critical guardrail paths must have tests.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.cost_guardrail import CostBudgetType, CostCheckResult, CostGuardrail


@pytest.fixture
def guardrail() -> CostGuardrail:
    return CostGuardrail()


class TestCostGuardrailAllowed:
    def test_cost_within_query_budget_is_allowed(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.05):
            result = guardrail.check(0.01, CostBudgetType.QUERY, "trace-1")
        assert result.allowed is True

    def test_cost_at_exact_limit_is_allowed(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.05):
            result = guardrail.check(0.05, CostBudgetType.QUERY, "trace-2")
        assert result.allowed is True

    def test_cost_within_eval_budget_is_allowed(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=1.00):
            result = guardrail.check(0.75, CostBudgetType.EVAL, "trace-3")
        assert result.allowed is True

    def test_cost_within_pipeline_build_budget_is_allowed(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=5.00):
            result = guardrail.check(2.50, CostBudgetType.PIPELINE_BUILD, "trace-4")
        assert result.allowed is True


class TestCostGuardrailBlocked:
    def test_cost_above_query_limit_is_blocked(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.01):
            result = guardrail.check(0.05, CostBudgetType.QUERY, "trace-5")
        assert result.allowed is False

    def test_blocked_result_has_reason(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.01):
            result = guardrail.check(0.05, CostBudgetType.QUERY, "trace-6")
        assert "exceeds" in result.reason
        assert "limit" in result.reason

    def test_blocked_result_carries_correct_budget_type(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.50):
            result = guardrail.check(1.00, CostBudgetType.EVAL, "trace-7")
        assert result.budget_type == CostBudgetType.EVAL

    def test_blocked_result_carries_correct_amounts(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=2.00):
            result = guardrail.check(3.00, CostBudgetType.PIPELINE_BUILD, "trace-8")
        assert result.estimated_cost_usd == 3.00
        assert result.budget_limit_usd == 2.00


class TestCostGuardrailReturnType:
    def test_returns_cost_check_result(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.05):
            result = guardrail.check(0.01, CostBudgetType.QUERY, "trace-9")
        assert isinstance(result, CostCheckResult)

    def test_allowed_result_has_within_budget_reason(self, guardrail: CostGuardrail) -> None:
        with patch.object(guardrail, "_get_limit", return_value=0.05):
            result = guardrail.check(0.01, CostBudgetType.QUERY, "trace-10")
        assert "budget" in result.reason
