"""Typed LangGraph state for one supervisor run (FinanceState)."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer for parallel agent branches: each writes its own key."""
    return {**(left or {}), **(right or {})}


class FinanceState(TypedDict, total=False):
    # request context
    request_id: str
    trace_id: str
    tenant_id: str
    user_id: str | None
    role: str
    question: str
    conversation_id: str | None
    history: list[dict[str, Any]]  # short-term memory: previous turns (oldest first)
    forced: dict[str, Any]  # structured API call: {"intent", "portfolio_id", "tickers"}
    # routing
    intent: str
    classification: dict[str, Any]
    portfolio_id: str | None
    tickers: list[str]
    assumptions: Annotated[list[str], operator.add]
    plan: list[list[str]]
    stage_index: int
    # agent work
    agent: str  # set on Send payloads only
    agent_results: Annotated[dict[str, dict[str, Any]], merge_dicts]
    errors: Annotated[list[str], operator.add]
    # answer
    blocked: bool
    guard_reason: str | None  # input block or permission denial (code)
    guard_message: str | None  # user-facing explanation
    guard_flags: Annotated[list[str], operator.add]
    narrative: str | None
    narrative_source: str  # llm | deterministic
    validation: dict[str, Any]
    report: dict[str, Any]
