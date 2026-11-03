"""Add result_evaluation_run_id to experiment_runs.

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-20 00:00:00.000000 UTC

Apply Improvement / Optimizer feature (20-Jul-2026): experiment_runs already
had result_pipeline_version_id (which version an applied variant produced),
but no link to the evaluation_runs row that scored that version -- so the
Pipeline Evolution UI had no real way to show latency/cost/recall per
version (evaluation_runs is the only table that carries those columns).
Nullable FK, ON DELETE SET NULL -- a deleted evaluation run must not corrupt
experiment_runs' own history.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_TABLE = "experiment_runs"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("result_evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_experiment_runs_result_evaluation_run_id",
        _TABLE,
        "evaluation_runs",
        ["result_evaluation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_experiment_runs_result_evaluation_run_id",
        _TABLE,
        ["result_evaluation_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_runs_result_evaluation_run_id", table_name=_TABLE)
    op.drop_constraint(
        "fk_experiment_runs_result_evaluation_run_id", _TABLE, type_="foreignkey"
    )
    op.drop_column(_TABLE, "result_evaluation_run_id")
