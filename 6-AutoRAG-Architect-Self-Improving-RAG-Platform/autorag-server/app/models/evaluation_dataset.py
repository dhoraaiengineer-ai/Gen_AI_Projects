"""ORM models -- evaluation_datasets, evaluation_dataset_versions, golden_questions.

Mirrors migration 0017. Immutability pattern (Rule 55): a dataset's mutable
container row (EvaluationDataset) never holds questions directly -- every
GoldenQuestion FKs to a specific EvaluationDatasetVersion, so publishing a
new version never rewrites the question set a past batch run was scored
against.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7

if TYPE_CHECKING:
    pass


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_evaluation_datasets_org_name"),
        CheckConstraint("status IN ('active','archived')", name="ck_evaluation_datasets_status"),
        Index("ix_evaluation_datasets_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[list[EvaluationDatasetVersion]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EvaluationDataset name={self.name} status={self.status}>"


class EvaluationDatasetVersion(Base):
    __tablename__ = "evaluation_dataset_versions"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "version_label", name="uq_evaluation_dataset_versions_dataset_label"
        ),
        CheckConstraint(
            "lifecycle_status IN ('draft','under_review','published','archived')",
            name="ck_evaluation_dataset_versions_lifecycle_status",
        ),
        Index("ix_evaluation_dataset_versions_dataset_id", "dataset_id"),
        Index("ix_evaluation_dataset_versions_organization_id", "organization_id"),
        Index("ix_evaluation_dataset_versions_lifecycle_status", "lifecycle_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="draft"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset: Mapped[EvaluationDataset] = relationship(back_populates="versions")
    questions: Mapped[list[GoldenQuestion]] = relationship(
        back_populates="dataset_version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<EvaluationDatasetVersion dataset_id={self.dataset_id} "
            f"label={self.version_label} status={self.lifecycle_status}>"
        )


class GoldenQuestion(Base):
    __tablename__ = "golden_questions"
    __table_args__ = (
        CheckConstraint(
            "difficulty IS NULL OR difficulty IN ('easy','medium','hard','expert')",
            name="ck_golden_questions_difficulty",
        ),
        CheckConstraint(
            "review_status IN ('draft','under_review','approved','rejected','archived')",
            name="ck_golden_questions_review_status",
        ),
        Index("ix_golden_questions_dataset_version_id", "dataset_version_id"),
        Index("ix_golden_questions_organization_id", "organization_id"),
        Index("ix_golden_questions_review_status", "review_status"),
        Index("ix_golden_questions_category", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text(), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reference_answer: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expected_context: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reference_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    reference_pages: Mapped[str | None] = mapped_column(String(100), nullable=True)
    relevant_chunk_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metric_focus: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="draft"
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    dataset_version: Mapped[EvaluationDatasetVersion] = relationship(back_populates="questions")

    def __repr__(self) -> str:
        return f"<GoldenQuestion id={self.id} review_status={self.review_status}>"
