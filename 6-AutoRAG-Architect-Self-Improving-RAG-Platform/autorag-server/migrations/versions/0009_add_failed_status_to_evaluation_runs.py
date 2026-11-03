"""Add 'failed' to ck_evaluation_runs_status.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-12 00:00:00.000000 UTC

The evaluation background task (app/routes/evaluate.py::_run_eval_workflow)
persists status='failed' when the LangGraph workflow raises, but the original
migration 0002 CHECK constraint only allowed
('pending','running','completed','blocked') -- so every workflow failure hit
a CheckViolationError on the recovery write itself, leaving the run stuck at
'pending' forever with no way for GET /jobs/{id} to ever report a terminal
state. See verification/releases/v4.0/full_api_contract_audit_11jul2026.md follow-up.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None

_OLD_STATUSES = "('pending','running','completed','blocked')"
_NEW_STATUSES = "('pending','running','completed','blocked','failed')"


def upgrade() -> None:
    op.drop_constraint("ck_evaluation_runs_status", "evaluation_runs", type_="check")
    op.create_check_constraint(
        "ck_evaluation_runs_status",
        "evaluation_runs",
        sa.text(f"status IN {_NEW_STATUSES}").text,
    )


def downgrade() -> None:
    op.drop_constraint("ck_evaluation_runs_status", "evaluation_runs", type_="check")
    op.create_check_constraint(
        "ck_evaluation_runs_status",
        "evaluation_runs",
        sa.text(f"status IN {_OLD_STATUSES}").text,
    )
