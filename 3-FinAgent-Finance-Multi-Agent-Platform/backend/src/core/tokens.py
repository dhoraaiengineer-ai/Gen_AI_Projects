"""Token budgets (ADR-029): per-call input/output limits and a per-request ceiling.

* ``estimate_tokens`` — fast, dependency-free estimate (~4 characters per token for English/JSON);
  provider-reported usage is still what metrics and the request meter record.
* ``trim_to_tokens`` — keeps the head of a text within a token budget.
* ``RequestTokenMeter`` — accumulates provider-reported tokens for one request (context variable);
  once ``max_total`` is reached, further LLM calls are refused with ``BudgetExceeded`` so callers
  switch to their deterministic path instead of spending more.
"""

from __future__ import annotations

import math
from contextvars import ContextVar
from dataclasses import dataclass, field

from src.core.errors import AppError

CHARS_PER_TOKEN = 4


class BudgetExceeded(AppError):
    status_code = 429
    code = "token_budget_exceeded"
    retryable = False


@dataclass(frozen=True)
class CallBudget:
    """Limits for one kind of LLM call."""

    max_input_tokens: int
    max_output_tokens: int
    min_output_tokens: int = 0


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN) if text else 0


def trim_to_tokens(text: str, max_tokens: int, marker: str = " …[trimmed]") -> str:
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(marker))] + marker


def fit_lines(lines: list[str], max_tokens: int) -> list[str]:
    """Keep whole lines, in order, until the token budget is used."""
    kept: list[str] = []
    used = 0
    for line in lines:
        cost = estimate_tokens(line) + 1
        if used + cost > max_tokens:
            break
        kept.append(line)
        used += cost
    return kept


@dataclass
class RequestTokenMeter:
    max_total: int
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    cost_usd: float = 0.0
    models: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out

    def ensure_available(self) -> None:
        if self.total >= self.max_total:
            raise BudgetExceeded(
                "request token budget exhausted",
                details={"used": self.total, "budget": self.max_total},
            )

    def record(self, model: str, tokens_in: int, tokens_out: int, cost_usd: float) -> None:
        self.calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.cost_usd += cost_usd
        if model not in self.models:
            self.models.append(model)

    def summary(self) -> dict[str, object]:
        return {
            "llmCalls": self.calls,
            "tokensIn": self.tokens_in,
            "tokensOut": self.tokens_out,
            "tokensTotal": self.total,
            "tokenBudget": self.max_total,
            "estimatedCostUsd": round(self.cost_usd, 6),
            "models": list(self.models),
        }


_meter: ContextVar[RequestTokenMeter | None] = ContextVar("token_meter", default=None)


def current_meter() -> RequestTokenMeter | None:
    return _meter.get()


def start_meter(max_total: int) -> tuple[RequestTokenMeter, object]:
    meter = RequestTokenMeter(max_total=max_total)
    return meter, _meter.set(meter)


def stop_meter(token: object) -> None:
    _meter.reset(token)  # type: ignore[arg-type]
