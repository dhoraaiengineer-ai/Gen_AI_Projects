"""ORM model — deployments table (ECS Fargate Blue/Green deploy tracking).

Critical rules:
- task_arn must be an immutable SHA tag — never 'latest'
- rollback_task_arn preserves the previous Blue task ARN for instant revert
- unified_score_at_deploy is snapshotted — cannot change post-deploy

Mirrors migrations 0002 (table + ck_deployments_status) and 0003 (indexes).
The evaluation_run_id FK has no ON DELETE action (RESTRICT) — a deployment
must always trace back to the evaluation that authorised it.
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
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun
    from app.models.pipeline import Pipeline


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','blue_green','promoted','rolled_back','failed')",
            name="ck_deployments_status",
        ),
        Index("ix_deployments_pipeline_id", "pipeline_id"),
        Index("ix_deployments_organization_id", "organization_id"),
        Index("ix_deployments_evaluation_run_id", "evaluation_run_id"),
        Index("ix_deployments_status", "status"),
        Index("ix_deployments_created_at", "created_at"),
        Index("ix_deployments_org_pipeline", "organization_id", "pipeline_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # ECS task ARN — MUST be an immutable SHA tag (e.g. sha256:abc123)
    task_arn: Mapped[str] = mapped_column(String(500), nullable=False)
    # Previous Blue task ARN — kept for instant rollback
    rollback_task_arn: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
        # values: pending | blue_green | promoted | rolled_back | failed
    )

    # Snapshot of score at deploy time (non-mutable after creation)
    unified_score_at_deploy: Mapped[float | None] = mapped_column(
        Numeric(4, 3), nullable=True
    )

    # Canary window timestamps
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    pipeline: Mapped[Pipeline] = relationship(back_populates="deployments")
    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="deployment")

    def __repr__(self) -> str:
        return f"<Deployment id={self.id} status={self.status} score={self.unified_score_at_deploy}>"
