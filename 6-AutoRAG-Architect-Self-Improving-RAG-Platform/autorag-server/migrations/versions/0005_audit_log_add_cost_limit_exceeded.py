"""Add cost_limit_exceeded to audit_log check constraint.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17 00:00:00.000000 UTC

Rule 86: CostGuardrail budget breach must be written to audit_log with
event_type='cost_limit_exceeded'. The APPROVED_EVENT_TYPES frozenset in
app/models/audit_log.py already includes this value; this migration syncs
the DB-level CHECK constraint to match (was 11 values, now 12).
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_audit_log_event_type", "audit_log", type_="check")
    op.create_check_constraint(
        "ck_audit_log_event_type",
        "audit_log",
        "event_type IN ("
        "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
        "'eval_started','eval_completed','deploy_started','deploy_completed',"
        "'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_log_event_type", "audit_log", type_="check")
    op.create_check_constraint(
        "ck_audit_log_event_type",
        "audit_log",
        "event_type IN ("
        "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
        "'eval_started','eval_completed','deploy_started','deploy_completed',"
        "'rollback_triggered','hitl_approved','hitl_rejected'"
        ")",
    )
