"""LangGraph checkpoint tables (human-approval pauses survive restarts) with RLS enabled.

The SQL is LangGraph's own (``BasePostgresSaver.MIGRATIONS``), recorded in
``checkpoint_migrations`` so ``AsyncPostgresSaver.setup()`` at runtime is a no-op. Indexes are
built without CONCURRENTLY because Alembic runs inside a transaction. RLS is enabled with no
policy: only the API's database role (table owner) can read checkpoints.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from langgraph.checkpoint.postgres.base import BasePostgresSaver

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes")


def upgrade() -> None:
    for version, statement in enumerate(BasePostgresSaver.MIGRATIONS):
        op.execute(statement.replace("CONCURRENTLY ", ""))
        op.execute(
            f"INSERT INTO checkpoint_migrations (v) VALUES ({version}) ON CONFLICT (v) DO NOTHING"
        )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
