"""graph_node_runs — per-node idempotency for the service graph (rules/60, P3-7)

A node run is keyed by (ro_id, node, input_hash). Re-running a node with identical inputs returns the stored output
and writes nothing else, so "run the workflow twice" leaves the DB unchanged. RLS is enabled (ADR-007, MEMORY L-004).

Revision ID: f6a7b8c9d004
Revises: e5f6a7b8c903
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d004"
down_revision: str | None = "e5f6a7b8c903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_node_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ro_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repair_orders.id"), nullable=False),
        sa.Column("node", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("ro_id", "node", "input_hash", name="uq_graph_node_runs_key"),
    )
    op.execute("ALTER TABLE public.graph_node_runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("graph_node_runs")
