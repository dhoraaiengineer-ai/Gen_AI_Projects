"""Knowledge base: documents, chunks (pgvector + full text), KB state, seed state."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import CHUNK_LEVELS, CLASSIFICATIONS, DOC_TYPES, DOCUMENT_STATUSES
from src.db.base import EMBEDDING_DIMENSIONS, Base, TenantScoped, TimestampMixin, in_list


class Document(TenantScoped, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source"),
        CheckConstraint(in_list("doc_type", DOC_TYPES), name="doc_type"),
        CheckConstraint(in_list("classification", CLASSIFICATIONS), name="classification"),
        CheckConstraint(in_list("status", DOCUMENT_STATUSES), name="status"),
        CheckConstraint(
            "expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date",
            name="date_order",
        ),
        Index("ix_documents_filters", "doc_type", "ticker", "fiscal_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(12), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(10))
    fiscal_period: Mapped[str | None] = mapped_column(String(12))
    classification: Mapped[str] = mapped_column(String(12), nullable=False, default="internal")
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="processing")
    strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    error: Mapped[str | None] = mapped_column(String(500))
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class DocumentChunk(TenantScoped, Base):
    """Chunk with bi-encoder embedding and generated full-text vector.

    Filter columns are denormalised from ``documents`` so both searches pre-filter in SQL.
    Parents (``level='parent'``) may have no embedding; children point to them.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint(in_list("level", CHUNK_LEVELS), name="level"),
        CheckConstraint(in_list("doc_type", DOC_TYPES), name="doc_type"),
        CheckConstraint(in_list("classification", CLASSIFICATIONS), name="classification"),
        CheckConstraint("token_count >= 0", name="token_count"),
        Index("ix_document_chunks_document", "document_id", "ordinal"),
        Index(
            "ix_document_chunks_filters", "classification", "doc_type", "ticker", "fiscal_period"
        ),
        Index("ix_document_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False, default="leaf")
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_header: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    location: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(context_header, '') || ' ' || content)", persisted=True
        ),
    )
    doc_type: Mapped[str] = mapped_column(String(12), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(10))
    fiscal_period: Mapped[str | None] = mapped_column(String(12))
    classification: Mapped[str] = mapped_column(String(12), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KbState(Base):
    """One row per tenant: knowledge-base version (bumped on every change) and embedding model."""

    __tablename__ = "kb_state"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SeedState(Base):
    """Singleton row recording which synthetic dataset version is loaded (idempotent seed)."""

    __tablename__ = "seed_state"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    row_counts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    seeded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
