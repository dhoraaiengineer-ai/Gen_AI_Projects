"""CostGuardrail — single enforcement point for per-query / per-run cost budgets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CostBudgetType(StrEnum):
    """Budget scope — each maps to a distinct env var (Rule 86 §13)."""
    QUERY = "query"
    EVAL = "eval"
    PIPELINE_BUILD = "pipeline_build"


@dataclass
class CostCheckResult:
    """Result of a CostGuardrail.check() call."""
    allowed: bool
    budget_type: CostBudgetType
    estimated_cost_usd: float
    budget_limit_usd: float
    reason: str


class CostGuardrailError(Exception):
    """Raised when cost budget is exceeded and caller must halt."""


class CostGuardrail:
    """Enforces per-operation cost budgets loaded from environment variables."""

    def _get_limit(self, budget_type: CostBudgetType) -> float:
        """Read budget limit from env vars — never hardcoded (Rule 86 §13)."""
        settings = get_settings()
        mapping: dict[CostBudgetType, str] = {
            CostBudgetType.QUERY: "max_query_cost_usd",
            CostBudgetType.EVAL: "max_eval_cost_usd",
            CostBudgetType.PIPELINE_BUILD: "max_pipeline_build_usd",
        }
        attr = mapping[budget_type]
        return float(getattr(settings, attr, _SAFE_DEFAULTS[budget_type]))

    def check(
        self,
        estimated_cost_usd: float,
        budget_type: CostBudgetType,
        x_trace_id: str,
    ) -> CostCheckResult:
        """Check whether the estimated cost fits within the configured budget."""
        limit = self._get_limit(budget_type)
        allowed = estimated_cost_usd <= limit

        result = CostCheckResult(
            allowed=allowed,
            budget_type=budget_type,
            estimated_cost_usd=estimated_cost_usd,
            budget_limit_usd=limit,
            reason=(
                "within budget"
                if allowed
                else f"cost ${estimated_cost_usd:.6f} exceeds {budget_type.value} limit ${limit:.6f}"
            ),
        )

        log_level = logger.info if allowed else logger.warning
        log_level(
            "cost_guardrail_check",
            extra={
                "allowed": allowed,
                "budget_type": budget_type.value,
                "estimated_cost_usd": estimated_cost_usd,
                "budget_limit_usd": limit,
                "x_trace_id": x_trace_id,
            },
        )

        return result


_SAFE_DEFAULTS: dict[CostBudgetType, float] = {
    CostBudgetType.QUERY: 0.05,
    CostBudgetType.EVAL: 1.00,
    CostBudgetType.PIPELINE_BUILD: 5.00,
}
