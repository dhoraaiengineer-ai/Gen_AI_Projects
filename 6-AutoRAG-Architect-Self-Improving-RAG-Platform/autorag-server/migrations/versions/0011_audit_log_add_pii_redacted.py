"""Add pii_redacted to audit_log check constraint.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-13 00:00:00.000000 UTC

Rule 70 + P0.7-2 (Unified PII Boundary): PII masking previously produced no
permanent audit evidence anywhere -- only a DEBUG-level redaction-count log
line (app/guardrails/input/pii_detector.py) or nothing at all
(app/services/pii_service.py). METRICS_WIRING_MATRIX.md flagged this as a
D/E gap ("PII detection events are untraceable"). This migration adds
pii_redacted as the 14th approved event_type so successful redaction (never
a block -- see P0.7-4) has a real, INSERT-ONLY audit trail: safe metadata
only (counts_by_type, total_redaction_count, source, detector_version) --
never the original PII value, never a truncated sample.

The APPROVED_EVENT_TYPES frozenset in app/models/audit_log.py already
includes this value after this migration. The DB-level CHECK constraint is
updated here (was 13 values, now 14).
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_CONSTRAINT_NAME = "ck_audit_log_event_type"
_TABLE = "audit_log"

_V14 = (
    "event_type IN ("
    "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
    "'eval_started','eval_completed','deploy_started','deploy_completed',"
    "'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded',"
    "'guardrail_blocked','pii_redacted'"
    ")"
)

_V13 = (
    "event_type IN ("
    "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
    "'eval_started','eval_completed','deploy_started','deploy_completed',"
    "'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded',"
    "'guardrail_blocked'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT_NAME, _TABLE, _V14)


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT_NAME, _TABLE, _V13)
