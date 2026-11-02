"""documents, extracted_fields, checklist_items."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, in_list, updated_at, uuid_pk

DOC_CLASSES = (
    "repair_order",
    "parts_invoice",
    "service_record",
    "warranty_claim_form",
    "diagnostic_report",
    "odometer_photo",
    "inspection_photo",
    "other",
)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("ro_id", "sha256", name="uq_documents_ro_sha256"),
        CheckConstraint(in_list("mime", ("application/pdf", "image/jpeg", "image/png")), name="mime_valid"),
        CheckConstraint(f"doc_class IS NULL OR {in_list('doc_class', DOC_CLASSES)}", name="doc_class_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    mime: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int] = mapped_column(Integer, default=1)
    sha256: Mapped[str] = mapped_column(String(64))
    doc_class: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    av_status: Mapped[str] = mapped_column(String(16), default="pending")  # DEMO AV hook
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(in_list("validation_status", ("ok", "failed", "not_checked")), name="validation_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    value: Mapped[str | None] = mapped_column(Text)  # may be PII
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    source_page: Mapped[int] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(16), default="not_checked")
    needs_human_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    previous_value: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    edit_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    __table_args__ = (
        CheckConstraint("ro_id IS NOT NULL OR claim_id IS NOT NULL", name="has_parent"),
        CheckConstraint(in_list("status", ("present", "missing", "unreadable", "inconsistent")), name="status_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warranty_claims.id"), index=True)
    item_code: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    source_chunk_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
