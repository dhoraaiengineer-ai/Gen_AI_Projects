"""LangGraph PostgresSaver tables, owned by Alembic (P3-3)

`AsyncPostgresSaver.setup()` creates these at runtime with `CREATE INDEX CONCURRENTLY`, which waits for every open
transaction in the database — called from inside an API request it deadlocked against that request's own session
(2026-10-28, MEMORY L-010). So the schema is created here, statically (copied from langgraph-checkpoint-postgres 3.2.0
migrations v0–v9; tables are empty at creation, so plain CREATE INDEX is fine), and the runtime never calls setup().
On a LangGraph upgrade that adds checkpoint migrations, add a new Alembic revision.

Revision ID: g7b8c9d0e105
Revises: f6a7b8c9d004
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g7b8c9d0e105"
down_revision: str | None = "f6a7b8c9d004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS checkpoint_migrations (v INTEGER PRIMARY KEY)",
    """CREATE TABLE IF NOT EXISTS checkpoints (
        thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '', checkpoint_id TEXT NOT NULL,
        parent_checkpoint_id TEXT, type TEXT, checkpoint JSONB NOT NULL, metadata JSONB NOT NULL DEFAULT '{}',
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id))""",
    """CREATE TABLE IF NOT EXISTS checkpoint_blobs (
        thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '', channel TEXT NOT NULL, version TEXT NOT NULL,
        type TEXT NOT NULL, blob BYTEA, PRIMARY KEY (thread_id, checkpoint_ns, channel, version))""",
    """CREATE TABLE IF NOT EXISTS checkpoint_writes (
        thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '', checkpoint_id TEXT NOT NULL,
        task_id TEXT NOT NULL, idx INTEGER NOT NULL, channel TEXT NOT NULL, type TEXT, blob BYTEA NOT NULL,
        task_path TEXT NOT NULL DEFAULT '', PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx))""",
    "CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id)",
    "CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id)",
    "CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id)",
    # tell the library all of its migrations v0–v9 are applied, so a later setup() is a no-op
    "INSERT INTO checkpoint_migrations (v) SELECT generate_series(0, 9) ON CONFLICT DO NOTHING",
    *[
        f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY"  # ADR-007 / MEMORY L-004: no Data-API access
        for t in ("checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes")
    ],
]


def upgrade() -> None:
    for sql in STATEMENTS:
        op.execute(sql)


def downgrade() -> None:
    for t in ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations"):
        op.execute(f"DROP TABLE IF EXISTS {t}")
