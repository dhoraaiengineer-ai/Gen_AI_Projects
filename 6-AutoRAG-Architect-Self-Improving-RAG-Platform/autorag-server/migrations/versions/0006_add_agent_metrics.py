"""Add agent_metrics table for per-node LLM cost and latency tracking.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-19

Approved by Mahesh Kumar (Project Lead) on 02-Jul-2026 — ADR-006.
    DB_SCHEMA.md v1.0 addendum: agent_metrics table now documented.

    To apply:
        cd autorag-server && uv run alembic upgrade 0006

    To roll back:
        cd autorag-server && uv run alembic downgrade 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create agent_metrics table — per-node LLM cost + latency records."""
    op.create_table(
        "agent_metrics",
        # Primary key — UUID v7 (time-sortable, Rule 30)
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        # Tenant isolation — all queries must include organization_id (Rule 30)
        sa.Column("organization_id", sa.UUID(), nullable=False),
        # LangGraph run correlation
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("x_trace_id", sa.Text(), nullable=False),
        # Agent and provider identity
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        # Token counts (Rule 86 §1)
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "completion_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        # Cost in USD — 8 decimal places (Rule 86 §1)
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=12, scale=8),
            nullable=False,
            server_default="0",
        ),
        # Latency in milliseconds
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        # Soft-delete (Rule 30 — never hard-delete audit-related rows)
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # FK — organization must exist; cascade on org deletion (ADR-006 decision 4)
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_agent_metrics_organization_id",
            ondelete="CASCADE",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_agent_metrics_organization_id",
        "agent_metrics",
        ["organization_id"],
    )
    op.create_index(
        "ix_agent_metrics_run_id",
        "agent_metrics",
        ["run_id"],
    )
    op.create_index(
        "ix_agent_metrics_x_trace_id",
        "agent_metrics",
        ["x_trace_id"],
    )
    op.create_index(
        "ix_agent_metrics_created_at",
        "agent_metrics",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop agent_metrics table — fully reversible."""
    op.drop_index("ix_agent_metrics_created_at", table_name="agent_metrics")
    op.drop_index("ix_agent_metrics_x_trace_id", table_name="agent_metrics")
    op.drop_index("ix_agent_metrics_run_id", table_name="agent_metrics")
    op.drop_index("ix_agent_metrics_organization_id", table_name="agent_metrics")
    op.drop_table("agent_metrics")
