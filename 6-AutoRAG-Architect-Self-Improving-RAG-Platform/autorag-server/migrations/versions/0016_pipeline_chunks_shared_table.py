"""Immutable versioned indexes -- shared pipeline_chunks table.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-20 00:00:00.000000 UTC

Architectural fix (20-Jul-2026, Version 4): the per-version physical table
convention (autorag_{pipeline_id}_{version}, docs/DB_SCHEMA.md frozen
contract) was never actually reachable by real version increments --
GraphState.pipeline_version (the string that drove table naming) was never
derived from pipelines.current_version anywhere in the codebase, so every
Apply Improvement rebuild silently wrote into the SAME physical table
(always "v1.0"), accumulating chunks instead of isolating them, and
"rollback" only flipped a config pointer without touching any real vector
data. Root cause found via a real integration test run against Supabase
Cloud dev (see .claude/MEMORY.md L-011 session, 20-Jul-2026).

Replacement design ("immutable versioned indexes"): one real, Alembic-
managed table (pipeline_chunks) shared across every pipeline and version,
partitioned logically by a `pipeline_version` column instead of physically
by table name. Every query filters by (organization_id, pipeline_id,
pipeline_version) -- the same scoping pattern every other multi-tenant table
in this schema already uses (pipelines, evaluation_runs, etc. are shared
tables filtered by organization_id, not per-org physical tables). Benefits:
  - Apply Improvement's rebuild writes NEW rows tagged with the NEW version
    string -- the OLD version's rows are untouched, giving real isolation.
  - Rollback becomes a single UPDATE pipelines SET current_version = X --
    no rebuild, no copy, no delete. The old version's rows are still there.
  - No table-per-version explosion (hundreds of pipelines x N versions each
    would otherwise mean hundreds of tables, each needing its own HNSW
    index, vacuum, and permissions).

chunk_id is deterministic (app/rag/chunking/base.py deterministic_chunk_id,
P0.5-2) -- derived from (organization_id, source_uri, chunk_strategy,
page_number, chunk_index), where source_uri already embeds pipeline_id via
its storage path. The composite unique constraint below adds
pipeline_version so the SAME chunk re-ingested under the SAME version is a
real idempotent upsert, while a NEW version's chunks (even if content is
identical) are correctly isolated as new rows.

Data migration (best-effort, additive only): every real pipeline created
before this fix ingested under the literal hardcoded string "v1.0" (the old
initial_state() default, never overridden by any caller), which the OLD
_table_name() convention sanitized to a table suffix of "v1_0". This
migration computes that exact legacy table name per real pipeline row, and
if it exists, copies its rows into pipeline_chunks tagged pipeline_version
="v1" (the new canonical format -- see app.core.state.format_pipeline_version).
Old per-version tables are left in place untouched (not dropped) -- a
manual cleanup step, not something this migration should do automatically
against live data this close to a demo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_EMBEDDING_DIM = 768
_HNSW_M = 16
_HNSW_EF_CONSTRUCTION = 200


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    bind.execute(
        text(f"""
            CREATE TABLE IF NOT EXISTS pipeline_chunks (
                id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                pipeline_id     UUID        NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
                pipeline_version TEXT       NOT NULL,
                chunk_id        TEXT        NOT NULL,
                chunk_text      TEXT        NOT NULL,
                chunk_strategy  TEXT        NOT NULL,
                page_number     INTEGER     NOT NULL,
                source_uri      TEXT        NOT NULL,
                parent_chunk_id TEXT,
                token_count     INTEGER     NOT NULL DEFAULT 0,
                chunk_index     INTEGER     NOT NULL DEFAULT 0,
                embedding       vector({_EMBEDDING_DIM}) NOT NULL,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_pipeline_chunks_pipeline_version_chunk
                    UNIQUE (pipeline_id, pipeline_version, chunk_id)
            )
        """)
    )

    bind.execute(
        text("""
            CREATE INDEX IF NOT EXISTS ix_pipeline_chunks_pipeline_version
            ON pipeline_chunks (pipeline_id, pipeline_version)
        """)
    )
    bind.execute(
        text("""
            CREATE INDEX IF NOT EXISTS ix_pipeline_chunks_organization_id
            ON pipeline_chunks (organization_id)
        """)
    )
    bind.execute(
        text(f"""
            CREATE INDEX IF NOT EXISTS ix_pipeline_chunks_embedding
            ON pipeline_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = {_HNSW_M}, ef_construction = {_HNSW_EF_CONSTRUCTION})
        """)
    )

    _migrate_legacy_per_version_tables(bind)


def _migrate_legacy_per_version_tables(bind: sa.engine.Connection) -> None:
    """Best-effort copy of every pre-existing autorag_{pipeline_id}_v1_0
    table's rows into pipeline_chunks, tagged pipeline_version='v1'. A
    missing/malformed legacy table for a given pipeline is skipped, not a
    migration failure -- most pipelines (drafts, never-ingested rows) never
    had one."""
    pipeline_ids = bind.execute(text("SELECT id FROM pipelines")).scalars().all()

    for pipeline_id in pipeline_ids:
        safe_id = str(pipeline_id).lower().replace("-", "_")
        legacy_table = f"autorag_{safe_id}_v1_0"

        exists = bind.execute(
            text("SELECT to_regclass(:t) IS NOT NULL"),
            {"t": legacy_table},
        ).scalar()
        if not exists:
            continue

        bind.execute(
            text(f"""
                INSERT INTO pipeline_chunks (
                    organization_id, pipeline_id, pipeline_version, chunk_id,
                    chunk_text, chunk_strategy, page_number, source_uri,
                    parent_chunk_id, token_count, chunk_index, embedding, created_at
                )
                SELECT
                    organization_id, :pipeline_id, 'v1', chunk_id,
                    chunk_text, chunk_strategy, page_number, source_uri,
                    parent_chunk_id, token_count, chunk_index, embedding, created_at
                FROM {legacy_table}
                ON CONFLICT (pipeline_id, pipeline_version, chunk_id) DO NOTHING
            """),  # noqa: S608 -- legacy_table computed above, no user input
            {"pipeline_id": pipeline_id},
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_chunks")
