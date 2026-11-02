"""Deterministic graph routing (P3-3): info_pending > recall_job > human_review (always reached for decisions)."""

from __future__ import annotations

from typing import Any

from app.graph.routing import route
from app.rules.config import load_rules

RULES = load_rules()
CLEAN: dict[str, Any] = {
    "intake": {"missing_fields": []},
    "documents": {"missing": [], "unreadable": [], "inconsistent": [], "unverified_fields": 0},
    "warranty": {"overall": "eligible", "findings": [{"rule_id": "W-RECALL-OVERLAP", "result": "pass", "inputs": {}}]},
    "estimate": {"estimable": True, "totals": {"grand": "2390.00"}, "lines": []},
    "risk": {"level": "low"},
}


def test_clean_route_still_needs_a_person() -> None:
    r = route(CLEAN, RULES)  # type: ignore[arg-type]
    assert r.next == "human_review" and r.reasons == ["binding decision requires a person"]


def test_missing_documents_and_unverified_fields_go_info_pending() -> None:
    s = CLEAN | {
        "documents": {
            "missing": ["parts_invoice"],
            "unreadable": ["odometer_photo"],
            "inconsistent": [],
            "unverified_fields": 2,
        }
    }
    r = route(s, RULES)  # type: ignore[arg-type]
    assert r.next == "info_pending"
    assert r.reasons == [
        "document missing: parts_invoice",
        "document unreadable: odometer_photo",
        "2 extracted field(s) need human verification",
    ]


def test_not_estimable_goes_info_pending() -> None:
    s = CLEAN | {"estimate": {"estimable": False, "not_estimable_reason": ["unknown op code OP-X"]}}
    assert route(s, RULES).next == "info_pending"  # type: ignore[arg-type]


def test_recall_overlap_goes_to_recall_job() -> None:
    overlap = {"rule_id": "W-RECALL-OVERLAP", "result": "fail", "inputs": {"open_recalls": ["RC-2025-01"]}}
    r = route(CLEAN | {"warranty": {"overall": "not_eligible", "findings": [overlap]}}, RULES)  # type: ignore[arg-type]
    assert r.next == "recall_job" and "RC-2025-01" in r.reasons[0]


def test_review_reasons_are_listed() -> None:
    s = CLEAN | {
        "risk": {"level": "high"},
        "warranty": {"overall": "unknown", "findings": []},
        "estimate": {
            "estimable": True,
            "totals": {"grand": str(RULES.review_amount_threshold.value + 1)},
            "lines": [{"pending_review": True}],
        },
        "safety_critical": True,
    }
    r = route(s, RULES)  # type: ignore[arg-type]
    assert r.next == "human_review" and len(r.reasons) == 6
