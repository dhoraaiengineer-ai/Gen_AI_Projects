"""ORM model -- audit_log table.

INSERT ONLY -- enforced at THREE levels:
  1. This model has no update() or delete() methods
  2. AuditLogRepository has no update/delete methods
  3. DB-level trigger (migration 0004) raises EXCEPTION on UPDATE/DELETE

Approved event_types (14 -- do not add without architect approval):
  pipeline_created, pipeline_updated, ingest_started, ingest_completed,
  eval_started, eval_completed, deploy_started, deploy_completed,
  rollback_triggered, hitl_approved, hitl_rejected,
  cost_limit_exceeded,
  guardrail_blocked  (added 03-Jul-2026 -- migration 0007)
  pii_redacted        (added 13-Jul-2026 -- migration 0011, P0.7-2)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7

# 14 approved event types -- do not add without architect approval.
APPROVED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "pipeline_created",
        "pipeline_updated",
        "ingest_started",
        "ingest_completed",
        "eval_started",
        "eval_completed",
        "deploy_started",
        "deploy_completed",
        "rollback_triggered",
        "hitl_approved",
        "hitl_rejected",
        "cost_limit_exceeded",  # Rule 86 -- CostGuardrail budget breach
        "guardrail_blocked",    # ai-guardrails.md Rule 4+9 -- injection block audit trail
        "pii_redacted",         # Rule 70 -- P0.7-2, successful redaction evidence (never a block)
    }
)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_organization_id", "organization_id"),
        Index("ix_audit_log_event_type", "event_type"),
        Index("ix_audit_log_run_id", "run_id"),
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_payload_gin", "payload", postgresql_using="gin"),
        Index("ix_audit_log_org_event_type", "organization_id", "event_type"),
        CheckConstraint(
            "event_type IN ("
            "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
            "'eval_started','eval_completed','deploy_started','deploy_completed',"
            "'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded',"
            "'guardrail_blocked','pii_redacted'"
            ")",
            name="ck_audit_log_event_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Python/ORM attribute is x_trace_id (Rule 86 naming); DB column stays
    # `trace_id` per API_SPEC.md's own layer-naming clarification (HTTP header
    # = X-Trace-ID, GraphState field = x_trace_id, DB column = trace_id).
    x_trace_id: Mapped[str | None] = mapped_column("trace_id", String(255), nullable=True)

    # No updated_at — INSERT ONLY, rows are immutable
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} event={self.event_type} org={self.organization_id}>"
