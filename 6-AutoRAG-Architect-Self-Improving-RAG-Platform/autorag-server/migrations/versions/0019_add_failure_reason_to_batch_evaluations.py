"""Add error_message, error_type, failed_at to batch_evaluations.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-26 00:00:00.000000 UTC

Closes a real gap: BatchEvaluationRepository.mark_failed() previously took no
error information at all -- a failed row only ever got status="failed". The
actual cause (rate limit, timeout, connection error) was logged server-side
and then lost, never persisted, never shown in the UI. Adds three nullable
columns so a failed question's reason survives past the log line.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batch_evaluations", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("batch_evaluations", sa.Column("error_type", sa.String(50), nullable=True))
    op.add_column(
        "batch_evaluations", sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("batch_evaluations", "failed_at")
    op.drop_column("batch_evaluations", "error_type")
    op.drop_column("batch_evaluations", "error_message")
