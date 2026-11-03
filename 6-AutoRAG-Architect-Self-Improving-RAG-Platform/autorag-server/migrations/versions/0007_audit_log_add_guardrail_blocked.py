"""Add guardrail_blocked to audit_log check constraint.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-03 00:00:00.000000 UTC

ai-guardrails.md Rule 4 + Rule 9: all guardrail block events must emit an
audit trail. Previously only a structured log was written because
guardrail_blocked was not in the 12 frozen approved event types.
Architecture Review approved 03-Jul-2026 -- adds it as the 13th type.

The APPROVED_EVENT_TYPES frozenset in app/models/audit_log.py already includes
this value after this migration. The DB-level CHECK constraint is updated here
(was 12 values, now 13).
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_CONSTRAINT_NAME = "ck_audit_log_event_type"
_TABLE = "audit_log"

_V13 = (
    "event_type IN ("
    "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
    "'eval_started','eval_completed','deploy_started','deploy_completed',"
    "'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded',"
    "'guardrail_blocked'"
    ")"
)

_V12 = (
    "event_type IN ("
    "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
    "'eval_started','eval_completed','deploy_started','deploy_completed',"
    "'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT_NAME, _TABLE, _V13)


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT_NAME, _TABLE, _V12)
