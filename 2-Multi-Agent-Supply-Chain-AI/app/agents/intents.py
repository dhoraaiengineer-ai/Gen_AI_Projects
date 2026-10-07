"""Intent classification schema, keyword fallback router and dependency-aware plans."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "full_recommendation",
    "stockout_risk",
    "reorder_quantity",
    "supplier_selection",
    "inventory_explanation",
    "demand_forecast",
    "shipment_status",
    "policy_question",
    "research",
    "out_of_scope",
]

KNOWLEDGE_TERMS = re.compile(
    r"policy|polic|contract|agreement|clause|procurement|sop|rule|approval|threshold|incoterm|terms|guarantee|credit|penalt|"
    r"payment|warrant|service level|premium|un3480|dangerous goods|escalat|declare|rate card|moq|minimum order"
)
SUPPLIER_NAMES = re.compile(
    r"kaito|meridian|nordvolt|pacific rim|atlas|sakura|lone star|rhine valley|harbor packaging|guardian|brightway|baltic"
)
SUPPLY_CHAIN_TERMS = re.compile(
    r"sku|stock|inventory|order|supplier|vendor|lead time|demand|forecast|shipment|shipping|freight|carrier|logistic|deliver|"
    r"warehouse|customs|batter(?:y|ies)|price|cost"
)
SKU_RE = re.compile(r"\bsku[-\s]?(\d{3,6})\b", re.I)


class Classification(BaseModel):
    """Structured output of the intent classifier."""

    intent: Intent = Field(description="The single best intent")
    skus: list[str] = Field(default_factory=list, description="SKUs mentioned, formatted SKU-123")
    standalone_question: str = Field(description="The question rewritten to be understandable without history")
    confidence: float = Field(ge=0, le=1, description="Confidence in the intent")


# Stages run in order; agents within a stage run in parallel (LangGraph Send).
PLANS: dict[str, list[list[str]]] = {
    "full_recommendation": [["demand", "rag"], ["inventory"], ["supplier", "logistics"]],
    "stockout_risk": [["inventory"]],
    "reorder_quantity": [["demand"], ["inventory"]],
    "supplier_selection": [["inventory"], ["supplier", "rag"]],
    "inventory_explanation": [["demand", "logistics"], ["inventory"]],
    "demand_forecast": [["demand"]],
    "shipment_status": [["logistics"]],
    "policy_question": [["rag"]],
    "research": [["research"]],
    "out_of_scope": [],
}

NEEDS_SKU = {"full_recommendation", "reorder_quantity", "supplier_selection", "inventory_explanation", "demand_forecast"}


def extract_skus(text: str) -> list[str]:
    return list(dict.fromkeys(f"SKU-{m}" for m in SKU_RE.findall(text)))


def keyword_route(message: str) -> Classification:
    """Deterministic fallback when the LLM classifier is unavailable."""
    m = message.lower()
    skus = extract_skus(message)
    if re.search(r"(complete|full|end-to-end|overall).*(recommend|plan)|recommendation for", m):
        intent: Intent = "full_recommendation"
    elif re.search(r"(how much|how many|quantity).*(reorder|order)|reorder", m):
        intent = "reorder_quantity"
    elif "why" in m and re.search(r"inventory|stock|low", m):
        intent = "inventory_explanation"
    elif re.search(r"supplier|vendor", m) and not re.search(r"policy|contract", m):
        intent = "supplier_selection"
    elif re.search(r"shipment|delayed|delivery|carrier|logistic", m):
        intent = "shipment_status"
    elif re.search(r"forecast|demand|next month", m):
        intent = "demand_forecast"
    elif re.search(r"risk|stockout|stock-out|running out", m):
        intent = "stockout_risk"
    elif KNOWLEDGE_TERMS.search(m) or SUPPLIER_NAMES.search(m):
        intent = "policy_question"
    elif re.search(r"news|market|industry|external|web", m):
        intent = "research"
    elif SUPPLY_CHAIN_TERMS.search(m):
        intent = "policy_question"  # supply-chain question without a specific intent: ask the knowledge base
    else:
        intent = "out_of_scope"
    return Classification(intent=intent, skus=skus, standalone_question=message, confidence=0.6)
