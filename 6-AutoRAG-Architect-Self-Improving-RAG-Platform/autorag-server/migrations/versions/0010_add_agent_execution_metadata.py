"""Add agent_execution_metadata JSONB to evaluation_runs.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-12 00:00:00.000000 UTC

Node-level execution status/timing (GraphState.execution_trace), Observer's
trend/alert signals, the Improver's full 3-variant candidate set, and
adversarial per-question failure detail are all genuinely computed during a
run today but discarded once the request returns -- confirmed via
verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md. One JSONB column instead of four,
to avoid schema bloat and avoid conflating with ragas_metrics/failure_taxonomy
(both already semantically committed columns).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("agent_execution_metadata", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_runs", "agent_execution_metadata")
