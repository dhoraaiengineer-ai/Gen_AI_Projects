"""ORM models -- batch_runs (header) and batch_evaluations (per-question ledger).

Mirrors migration 0017. batch_runs.status drives queue-state UI; a
batch_evaluations row is bulk-inserted as 'pending' for every golden question
before dispatch (batch_eval_service.start_batch_run), which is what makes
resume-after-interruption possible -- re-dispatch only rows still
'pending'/'failed'.
"""

from __future__ import annotations

import uuid
from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class BatchRun(Base):
    __tablename__ = "batch_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','completed','cancelled','failed')",
            name="ck_batch_runs_status",
        ),
        Index("ix_batch_runs_organization_id", "organization_id"),
        Index("ix_batch_runs_dataset_version_id", "dataset_version_id"),
        Index("ix_batch_runs_pipeline_id", "pipeline_id"),
        Index("ix_batch_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_configs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="queued")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<BatchRun id={self.id} status={self.status}>"


class BatchEvaluation(Base):
    __tablename__ = "batch_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "batch_run_id", "golden_question_id", name="uq_batch_evaluations_run_question"
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_batch_evaluations_status",
        ),
        CheckConstraint(
            "review_status IN ('unreviewed','approved','rejected','corrected')",
            name="ck_batch_evaluations_review_status",
        ),
        Index("ix_batch_evaluations_batch_run_id", "batch_run_id"),
        Index("ix_batch_evaluations_organization_id", "organization_id"),
        Index("ix_batch_evaluations_golden_question_id", "golden_question_id"),
        Index("ix_batch_evaluations_status", "status"),
        Index("ix_batch_evaluations_review_status", "review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    batch_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("batch_runs.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    golden_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("golden_questions.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_configs.id", ondelete="SET NULL"), nullable=True
    )
    evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="unreviewed"
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    corrected_answer: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Failure reason (V4, 26-Jul-2026) -- previously mark_failed() persisted
    # no error information at all; the real cause was logged then lost.
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<BatchEvaluation id={self.id} batch_run_id={self.batch_run_id} status={self.status}>"
