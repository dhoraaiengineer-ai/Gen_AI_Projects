"""ORM model — pipeline_versions table.

Immutable after creation — one row per pipeline version.

Version 4 (20-Jul-2026, migration 0016): vector_table_name no longer names a
real per-version physical table -- every version's chunks live in the single
shared pipeline_chunks table, partitioned by a pipeline_version column. This
column now stores that partition label ("pipeline_chunks:v{n}") so the
pre-existing UNIQUE constraint stays satisfiable; see
app/services/vector_service.py and app/services/pipeline_service.py.

Mirrors migrations 0002 (table + uq_pipeline_versions_pipeline_version +
uq_pipeline_versions_vector_table) and 0003 (indexes).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7


class PipelineVersion(Base):
    __tablename__ = "pipeline_versions"
    __table_args__ = (
        UniqueConstraint(
            "pipeline_id",
            "version_number",
            name="uq_pipeline_versions_pipeline_version",
        ),
        UniqueConstraint(
            "vector_table_name", name="uq_pipeline_versions_vector_table"
        ),
        Index("ix_pipeline_versions_pipeline_id", "pipeline_id"),
        Index("ix_pipeline_versions_organization_id", "organization_id"),
        Index("ix_pipeline_versions_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Shared-table partition label — "pipeline_chunks:v{version_number}" (Version 4)
    vector_table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_strategy: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="semantic"
    )
    chunk_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_overlap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="gemini-embedding-2"
    )
    retrieval_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # config snapshot at creation

    # Timestamps — immutable after insert (no updated_at)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    pipeline: Mapped[Pipeline] = relationship(back_populates="versions")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<PipelineVersion pipeline={self.pipeline_id} v={self.version_number} table={self.vector_table_name}>"
