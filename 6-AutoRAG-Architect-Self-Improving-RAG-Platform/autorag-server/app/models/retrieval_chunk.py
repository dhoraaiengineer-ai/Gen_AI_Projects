"""ORM model — retrieval_chunks table (metadata only; vectors live in pgvector).

Each row maps to one chunk in the shared pipeline_chunks table (Version 4.0,
migration 0016), partitioned by the pipeline_version column referenced via
pipeline_version_id below -- not a real per-version physical table. Mandatory
metadata columns per Rule 50: source_uri, chunk_strategy, page_number.

Mirrors migrations 0002 (table) and 0003 (indexes). content_hash supports
dedup; evaluation_run_id (SET NULL) links chunks surfaced during an eval.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class RetrievalChunk(Base):
    __tablename__ = "retrieval_chunks"
    __table_args__ = (
        Index("ix_retrieval_chunks_pipeline_version_id", "pipeline_version_id"),
        Index("ix_retrieval_chunks_organization_id", "organization_id"),
        Index("ix_retrieval_chunks_evaluation_run_id", "evaluation_run_id"),
        Index("ix_retrieval_chunks_source_uri", "source_uri"),
        Index("ix_retrieval_chunks_chunk_strategy", "chunk_strategy"),
        Index("ix_retrieval_chunks_parent_chunk_id", "parent_chunk_id"),
        Index("ix_retrieval_chunks_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    pipeline_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_versions.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )

    # Mandatory metadata (Rule 50)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. supabase://storage/{org_id}/{pipeline_id}/doc.pdf
    chunk_strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    # values: semantic | hierarchical | late
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Parent chunk ref (for hierarchical strategy)
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retrieval_chunks.id", ondelete="SET NULL"), nullable=True
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<RetrievalChunk id={self.id} strategy={self.chunk_strategy} page={self.page_number}>"
