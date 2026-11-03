"""Add 'pending_approval' to ck_evaluation_runs_status.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-17 00:00:00.000000 UTC

Same bug class migration 0009 already fixed once for 'failed': the evaluation
background task (app/routes/evaluate.py::_run_eval_workflow) persists
status='pending_approval' for HITL-band scores (0.70 <= unified_score < 0.85)
-- see app/routes/evaluate.py line 99, app/routes/jobs.py, app/main.py -- but
that status was never added to the CHECK constraint when HITL support was
introduced. Every HITL-band run hit a CheckViolationError on the final
success-persist write, leaving the run stuck at 'pending' forever with no way
for GET /jobs/{id} to ever report a terminal state -- live-confirmed
17-Jul-2026: a real evaluation run computed a correct unified_score=0.8325,
faithfulness=1.0, recall_at_5=1.0 in ~82s, then failed to persist with
`ck_evaluation_runs_status` violation, appearing externally as an indefinite
hang. See verification/releases/v4.0/readiness/MANUAL_TEST_LOG_17JUL2026.md.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | None = None
depends_on: str | None = None

_OLD_STATUSES = "('pending','running','completed','blocked','failed')"
_NEW_STATUSES = "('pending','running','completed','blocked','failed','pending_approval')"


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
