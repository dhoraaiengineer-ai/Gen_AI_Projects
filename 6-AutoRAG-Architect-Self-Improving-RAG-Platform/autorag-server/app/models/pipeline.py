"""ORM model — pipelines table.

Rules (CLAUDE.md § Forbidden Patterns):
- Soft-delete only — never hard-delete a pipeline row
- status='decommissioned' + audit_log entry before dropping vector table
- UUID v7 PK (time-sortable)
- organization_id index mandatory (multi-tenancy)

Mirrors migrations 0002 (table + uq_pipelines_org_name + ck_pipelines_status)
and 0003 (indexes).
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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.evaluation_run import EvaluationRun
    from app.models.pipeline_version import PipelineVersion


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_pipelines_org_name"),
        CheckConstraint(
            "status IN ('draft','pending','running','ready','failed','decommissioned')",
            name="ck_pipelines_status",
        ),
        Index("ix_pipelines_organization_id", "organization_id"),
        Index("ix_pipelines_status", "status"),
        Index("ix_pipelines_deleted_at", "deleted_at"),
        Index("ix_pipelines_created_at", "created_at"),
        Index("ix_pipelines_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
        # values: draft | pending | running | ready | failed | decommissioned
        # draft added 16-Jul-2026 (migration 0013): Configurator creates the
        # pipeline in 'draft' immediately after step 1 so document upload has
        # a real pipeline_id from the start, instead of only at wizard finish.
    )
    chunk_strategy: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        # values: semantic | hierarchical | late
    )
    embedding_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="gemini-embedding-2",
        # RULE: only gemini-embedding-2 permitted (768-dim)
    )
    config_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    unified_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )

    # Timestamps
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
    )  # soft-delete

    # Relationships
    versions: Mapped[list[PipelineVersion]] = relationship(back_populates="pipeline")
    evaluation_runs: Mapped[list[EvaluationRun]] = relationship(
        back_populates="pipeline"
    )
    deployments: Mapped[list[Deployment]] = relationship(back_populates="pipeline")

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id} name={self.name} status={self.status}>"
