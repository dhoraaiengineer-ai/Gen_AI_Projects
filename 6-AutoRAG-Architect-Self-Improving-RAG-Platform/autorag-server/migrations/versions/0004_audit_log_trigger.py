"""Create DB-level trigger to block UPDATE and DELETE on audit_log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-26 00:03:00.000000 UTC

This is the THIRD enforcement layer for audit_log INSERT ONLY:
  Layer 1 — ORM model  : AuditLog has no update() or delete() methods
  Layer 2 — Repository : AuditLogRepository has no update/delete methods
  Layer 3 — DB trigger : This migration — RAISES EXCEPTION at the database level

The trigger fires BEFORE any UPDATE or DELETE attempt and raises a PostgreSQL
exception with SQLSTATE P0001. This cannot be bypassed from application code.

Approved event_types (frozen — do not add without architect approval):
  pipeline_created, pipeline_updated, ingest_started, ingest_completed,
  eval_started, eval_completed, deploy_started, deploy_completed,
  rollback_triggered, hitl_approved, hitl_rejected
"""

from __future__ import annotations

from alembic import op


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None

# ── PL/pgSQL function body ───────────────────────────────────────────────────
_CREATE_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION block_audit_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'audit_log is INSERT ONLY — UPDATE and DELETE are permanently prohibited. '
        'Attempted operation: % on row id=%',
        TG_OP,
        COALESCE(OLD.id::text, 'unknown')
        USING ERRCODE = 'P0001';
    RETURN NULL;
END;
$$;
"""

_DROP_FUNCTION_SQL = "DROP FUNCTION IF EXISTS block_audit_log_mutation() CASCADE;"

_CREATE_UPDATE_TRIGGER_SQL = """\
CREATE TRIGGER trg_audit_log_block_update
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_mutation();
"""

_CREATE_DELETE_TRIGGER_SQL = """\
CREATE TRIGGER trg_audit_log_block_delete
BEFORE DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_mutation();
"""

_DROP_UPDATE_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS trg_audit_log_block_update ON audit_log;"
)
_DROP_DELETE_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS trg_audit_log_block_delete ON audit_log;"
)


def upgrade() -> None:
    # 1. Create the PL/pgSQL function that raises the exception
    op.execute(_CREATE_FUNCTION_SQL)

    # 2. Attach trigger for UPDATE attempts
    op.execute(_CREATE_UPDATE_TRIGGER_SQL)

    # 3. Attach trigger for DELETE attempts
    op.execute(_CREATE_DELETE_TRIGGER_SQL)


def downgrade() -> None:
    # Remove triggers first, then the function (CASCADE handles it but be explicit)
    op.execute(_DROP_UPDATE_TRIGGER_SQL)
    op.execute(_DROP_DELETE_TRIGGER_SQL)
    op.execute(_DROP_FUNCTION_SQL)
