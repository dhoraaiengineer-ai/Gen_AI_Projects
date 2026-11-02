"""warranty_claims, warranty_status_history, warranty_findings, risk_flags, review_decisions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, created_at, in_list, updated_at, uuid_pk
from app.models.enums import ClaimStatus, values

_STATUS_ACTORS = ("vehicle_owner", "service_advisor", "technician", "warranty_admin", "admin", "system")


class WarrantyClaim(Base):
    __tablename__ = "warranty_claims"
    __table_args__ = (
        Index("ix_warranty_claims_dealer_status", "dealer_id", "status"),
        CheckConstraint(in_list("status", values(ClaimStatus)), name="status_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    claim_ref: Mapped[str] = mapped_column(String(16), unique=True, server_default=text("next_claim_ref()"))
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    dealer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dealers.id"))
    status: Mapped[str] = mapped_column(String(32), default=ClaimStatus.DRAFT.value)
    component_group: Mapped[str | None] = mapped_column(String(64))
    failed_part_number: Mapped[str | None] = mapped_column(String(32))
    total_claimed: Mapped[Decimal | None] = mapped_column(Money)
    oem_ack: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # DEMO adapter acknowledgement
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class WarrantyStatusHistory(Base):
    __tablename__ = "warranty_status_history"
    __table_args__ = (
        Index("ix_warranty_status_history_claim_created", "claim_id", "created_at"),
        CheckConstraint(in_list("actor_role", _STATUS_ACTORS), name="actor_role_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warranty_claims.id"))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class WarrantyFinding(Base):
    __tablename__ = "warranty_findings"
    __table_args__ = (CheckConstraint(in_list("result", ("pass", "fail", "unknown")), name="result_valid"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warranty_claims.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(32))
    result: Mapped[str] = mapped_column(String(8))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_chunk_id: Mapped[str | None] = mapped_column(String(128))
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class RiskFlag(Base):
    __tablename__ = "risk_flags"
    __table_args__ = (
        CheckConstraint("ro_id IS NOT NULL OR claim_id IS NOT NULL", name="has_parent"),
        CheckConstraint(in_list("severity", ("low", "medium", "high")), name="severity_valid"),
        CheckConstraint(in_list("status", ("open", "reviewed", "dismissed")), name="status_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warranty_claims.id"), index=True)
    detector_id: Mapped[str] = mapped_column(String(8), index=True)
    severity: Mapped[str] = mapped_column(String(8))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text)  # always "indicator for review" wording
    status: Mapped[str] = mapped_column(String(16), default="open")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint("ro_id IS NOT NULL OR claim_id IS NOT NULL", name="has_parent"),
        CheckConstraint(in_list("kind", ("estimate_approval", "warranty_decision")), name="kind_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warranty_claims.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str | None] = mapped_column(Text)
    line_decisions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    evidence_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
