"""Deterministic routing after the Risk node (rules/60: never ask the LLM which edge to take).

  missing / unreadable / inconsistent documents, unverified fields, missing intake data, not estimable → info_pending
  open recall covers the failed part                                                               → recall_job
  otherwise                                                                                        → human_review
Human review is reached on EVERY other route (even a clean one): any binding decision needs a person. The reasons
(risk high, warranty unknown, amount over threshold, safety-critical, pending-review lines) are shown to the reviewer.
"""

from __future__ import annotations

from decimal import Decimal

from app.graph.state import ServiceGraphState
from app.rules.config import Rules
from app.schemas.graph import RouteOut


def route(state: ServiceGraphState, rules: Rules) -> RouteOut:
    intake, docs = state.get("intake") or {}, state.get("documents") or {}
    war, est, risk = state.get("warranty") or {}, state.get("estimate") or {}, state.get("risk") or {}

    info: list[str] = [f"missing: {m}" for m in intake.get("missing_fields", [])]
    info += [f"document missing: {d}" for d in docs.get("missing", [])]
    info += [f"document unreadable: {d}" for d in docs.get("unreadable", [])]
    info += [f"document inconsistent: {d}" for d in docs.get("inconsistent", [])]
    if docs.get("unverified_fields"):
        info.append(f"{docs['unverified_fields']} extracted field(s) need human verification")
    if est and not est.get("estimable", False):
        info += [f"not estimable: {r}" for r in est.get("not_estimable_reason", [])]
    if info:
        return RouteOut(next="info_pending", reasons=info)

    recall = next((f for f in war.get("findings", []) if f["rule_id"] == "W-RECALL-OVERLAP"), None)
    if recall and recall["result"] == "fail":
        campaigns = ", ".join(recall["inputs"].get("open_recalls", [])) or "an open recall"
        return RouteOut(
            next="recall_job", reasons=[f"failed part is covered by {campaigns} — recall job, not warranty"]
        )

    reasons: list[str] = []
    if risk.get("level") == "high":
        reasons.append("risk level high — see indicators for review")
    if war.get("overall") == "unknown":
        reasons.append("warranty inputs incomplete")
    grand = Decimal(est.get("totals", {}).get("grand", "0"))
    if grand > rules.review_amount_threshold.value:
        reasons.append(f"amount {grand} above review threshold {rules.review_amount_threshold.value}")
    if state.get("safety_critical"):
        reasons.append("safety-critical system involved")
    if any(ln.get("pending_review") for ln in est.get("lines", [])):
        reasons.append("lines pending warranty review")
    reasons.append("binding decision requires a person")
    return RouteOut(next="human_review", reasons=reasons)
