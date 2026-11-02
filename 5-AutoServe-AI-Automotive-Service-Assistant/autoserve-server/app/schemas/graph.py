"""Pydantic models for ServiceGraphState fields (specs/graph-state.md). Stored in state as JSON dicts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PayType = Literal["warranty", "recall", "customer"]


class ActorCtx(BaseModel):
    user_id: str | None
    role: str
    dealer_id: str | None


class TraceEntry(BaseModel):
    node: str
    started_at: datetime
    duration_ms: int
    outcome: Literal["ok", "cached", "degraded", "error", "skipped"]
    input_hash: str
    model: str | None = None
    note: str | None = None


class NodeError(BaseModel):
    node: str
    code: str
    message: str


class IntakeOut(BaseModel):
    ro_ref: str
    ro_status: str
    vehicle_id: str
    owner_id: str
    model: str
    model_year: int
    odometer_km: int | None
    complaint_text: str
    damage_notes: str | None
    missing_fields: list[str] = Field(default_factory=list)


class DocSummary(BaseModel):
    id: str
    doc_class: str | None
    status: str
    unverified_fields: list[str] = Field(default_factory=list)


class DocumentOut(BaseModel):
    docs: list[DocSummary]
    missing: list[str]
    unreadable: list[str]
    inconsistent: list[str]
    unverified_fields: int
    invoice_part_numbers: list[str] | None  # None = no parts invoice extracted
    source: str


class DiagnosisSummary(BaseModel):
    """The technician-confirmed finding (diagnostic_findings). The AI copilot never decides the cause."""

    finding_id: str | None
    confirmed_hypothesis: str | None
    dtcs: list[str] = Field(default_factory=list)
    op_codes: list[str] = Field(default_factory=list)
    parts: list[dict[str, str]] = Field(default_factory=list)  # [{part_number, qty}]
    actual_hours: str | None = None


class WarrantyFindingOut(BaseModel):
    rule_id: str
    result: Literal["pass", "fail", "unknown"]
    inputs: dict[str, Any]
    source: str


class WarrantyOut(BaseModel):
    claim_id: str | None
    component_group: str | None
    failed_part_number: str | None
    findings: list[WarrantyFindingOut]
    overall: Literal["eligible", "not_eligible", "partial", "unknown"]
    reasons: list[str]
    explanation: str
    ai_label: str


class EstimateLineOut(BaseModel):
    kind: Literal["labour", "part", "tax"]
    code: str | None
    description: str
    qty: str
    hours: str | None
    unit_price: str
    amount: str
    pay_type: PayType
    pending_review: bool = False
    reason: str = ""


class EstimateOut(BaseModel):
    estimable: bool
    not_estimable_reason: list[str] = Field(default_factory=list)
    lines: list[EstimateLineOut] = Field(default_factory=list)
    totals: dict[str, str] = Field(default_factory=dict)  # warranty, recall, customer, tax, grand
    summary: str = ""


class DetectionOut(BaseModel):
    detector_id: str
    status: Literal["flag", "clear", "not_evaluated"]
    severity: str
    evidence: dict[str, Any]
    explanation: str


class RiskOut(BaseModel):
    level: Literal["low", "medium", "high"]
    detections: list[DetectionOut]


class RouteOut(BaseModel):
    next: Literal["info_pending", "recall_job", "human_review", "stop"]
    reasons: list[str]


class ReviewDecision(BaseModel):
    actor: ActorCtx
    decision: str
    rationale: str | None = None
    line_decisions: list[dict[str, str]] | None = None  # [{code, decision: approved|declined}]
    decided_at: datetime
    decision_id: str


class ReviewOut(BaseModel):
    kind: Literal["estimate_approval", "warranty_decision"]
    reasons: list[str]
    evidence_hash: str
    allowed_decisions: list[str]
    required_roles: list[str]
    decision: ReviewDecision | None = None
