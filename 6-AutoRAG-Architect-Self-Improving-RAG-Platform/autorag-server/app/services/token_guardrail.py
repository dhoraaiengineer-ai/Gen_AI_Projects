"""TokenGuardrail — guards against context window expansion that exceeds token budgets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TokenBudgetType(StrEnum):
    """Token budget scope — each maps to a distinct env var."""
    PROMPT = "prompt"
    COMPLETION = "completion"
    CONTEXT = "context"


@dataclass
class TokenCheckResult:
    """Result of a TokenGuardrail.check() call."""
    allowed: bool
    budget_type: TokenBudgetType
    requested_tokens: int
    budget_limit: int
    reason: str


class TokenGuardrailError(Exception):
    """Raised when a token budget would be exceeded."""


class TokenGuardrail:
    """Enforces per-operation token limits loaded from environment variables."""

    def _get_limit(self, budget_type: TokenBudgetType) -> int:
        """Read token limit from env vars — never hardcoded (Rule 86 §13)."""
        settings = get_settings()
        mapping: dict[TokenBudgetType, str] = {
            TokenBudgetType.PROMPT: "max_prompt_tokens",
            TokenBudgetType.COMPLETION: "max_completion_tokens",
            TokenBudgetType.CONTEXT: "max_context_tokens",
        }
        attr = mapping[budget_type]
        return int(getattr(settings, attr, _SAFE_DEFAULTS[budget_type]))

    def check(
        self,
        requested_tokens: int,
        budget_type: TokenBudgetType,
        x_trace_id: str,
    ) -> TokenCheckResult:
        """Check whether requested_tokens fits within the configured limit."""
        limit = self._get_limit(budget_type)
        allowed = requested_tokens <= limit

        result = TokenCheckResult(
            allowed=allowed,
            budget_type=budget_type,
            requested_tokens=requested_tokens,
            budget_limit=limit,
            reason=(
                "within token budget"
                if allowed
                else f"{budget_type.value} tokens {requested_tokens} exceeds limit {limit}"
            ),
        )

        log_level = logger.info if allowed else logger.warning
        log_level(
            "token_guardrail_check",
            extra={
                "allowed": allowed,
                "budget_type": budget_type.value,
                "requested_tokens": requested_tokens,
                "budget_limit": limit,
                "x_trace_id": x_trace_id,
            },
        )

        return result


_SAFE_DEFAULTS: dict[TokenBudgetType, int] = {
    TokenBudgetType.PROMPT: 32000,
    TokenBudgetType.COMPLETION: 4096,
    TokenBudgetType.CONTEXT: 64000,
}
