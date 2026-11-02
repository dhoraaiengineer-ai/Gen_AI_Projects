"""retrieval filter indexes — btree expression indexes on the metadata fields every vector query filters on

Large corpora: HNSW + post-filtering can return too few rows when filters exclude most of the corpus. These
indexes let the planner pre-filter cheaply, and the retriever enables pgvector iterative scans
(`hnsw.iterative_scan = relaxed_order`, pgvector ≥ 0.8) so filtered top-k stays complete.

Revision ID: d4e5f6a7b802
Revises: c3d4e5f6a701
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b802"
down_revision: str | None = "c3d4e5f6a701"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = {
    "ix_knowledge_chunks_md_visibility": "((metadata->>'visibility'))",
    "ix_knowledge_chunks_md_model": "((metadata->>'model'))",
    "ix_knowledge_chunks_md_doc_type": "((metadata->>'doc_type'))",
    "ix_knowledge_chunks_md_section_id": "((metadata->>'section_id'))",
    "ix_knowledge_chunks_md_years": "(((metadata->>'model_year_from')::int), ((metadata->>'model_year_to')::int))",
}


def upgrade() -> None:
    for name, expr in INDEXES.items():
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON knowledge_chunks {expr}")


def downgrade() -> None:
    for name in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
