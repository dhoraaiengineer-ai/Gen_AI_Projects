"""ORM model — documents table.

Rules (CLAUDE.md § Forbidden Patterns):
- Soft-delete only — never hard-delete a document row (deleted_at pattern)
- UUID v7 PK (time-sortable)
- organization_id index mandatory (multi-tenancy)

`pipeline_id` is the FK — there is no separate `projects` table in V3
(see app/routes/projects.py "V3 demo bridge" docstring: pipelines ARE
projects from the frontend's perspective). The API layer serializes
`pipeline_id` as `project_id` to satisfy the frozen Document DTO
(API_SPEC.md v1.1 § Document) without introducing a redundant table.

Mirrors migration 0008, extended by migration 0012 (page_count/char_count/
pii_redaction_count/pii_counts_by_type -- P0.7 follow-up, 13-Jul-2026).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7

if TYPE_CHECKING:
    from app.models.pipeline import Pipeline


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','validating','chunking','embedding','indexed','failed','archived')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "embedding_status IN ('pending','processing','complete','failed')",
            name="ck_documents_embedding_status",
        ),
        Index("ix_documents_organization_id", "organization_id"),
        Index("ix_documents_pipeline_id", "pipeline_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_deleted_at", "deleted_at"),
        Index("ix_documents_uploaded_at", "uploaded_at"),
        Index("ix_documents_org_pipeline", "organization_id", "pipeline_id"),
        Index("ix_documents_tags_gin", "tags", postgresql_using="gin"),
        Index("ix_documents_categories_gin", "categories", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    storage_bucket: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="documents"
    )
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="uploaded",
        # values: uploaded | validating | chunking | embedding | indexed | failed | archived
    )
    embedding_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
        # values: pending | processing | complete | failed
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    indexed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Document-level ingestion evidence (migration 0012, 13-Jul-2026) --
    # persisted by ingestion_node once this document's real pages are parsed
    # and masked, never reconstructed from node_trace after the fact (that
    # stays per-run evidence; this is per-document evidence). Nullable
    # (not server_default=0) for page_count/char_count specifically because
    # "0" would be indistinguishable from "measured and genuinely empty" --
    # NULL means "not yet measured for this document."
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pii_redaction_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    pii_counts_by_type: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"EMAIL": 8, "SSN": 0} -- canonical PII types from pii_engine.py (P0.7-1)

    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    categories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # soft-delete / archive

    # Relationships
    pipeline: Mapped[Pipeline] = relationship()

    def __repr__(self) -> str:
        return f"<Document id={self.id} file_name={self.file_name} status={self.status}>"
