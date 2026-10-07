"""Shared LangGraph state. List fields use reducers so parallel branches merge safely."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


class SupplyChainState(TypedDict, total=False):
    # request
    run_id: str
    request_id: str
    user: dict[str, Any]  # {id, name, role}
    user_query: str  # guarded (redacted) question
    history: list[dict[str, str]]  # recent conversation turns (memory)

    # routing
    intent: str
    standalone_question: str
    skus: list[str]
    classifier_confidence: float
    plan: list[list[str]]
    stage: int

    # specialist outputs
    demand_forecast: dict[str, Any]
    inventory_data: dict[str, Any]
    supplier_data: dict[str, Any]
    logistics_data: dict[str, Any]
    research_data: dict[str, Any]
    retrieved_documents: Annotated[list[dict[str, Any]], operator.add]
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    agent_notes: Annotated[dict[str, str], merge_dicts]
    errors: Annotated[list[dict[str, Any]], operator.add]

    # output
    blocked: bool
    block_message: str
    recommendation: str
    report: dict[str, Any]
    approval: dict[str, Any] | None
    approval_decision: dict[str, Any] | None
