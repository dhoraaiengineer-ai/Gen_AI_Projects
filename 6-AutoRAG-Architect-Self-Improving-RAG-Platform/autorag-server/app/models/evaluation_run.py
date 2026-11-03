"""ORM model — evaluation_runs table.

Critical rules (CLAUDE.md § Deployment Governance):
- faithfulness < 0.5 → hard block (enforced in service layer)
- unified_score >= 0.85 → deploy eligible
- adversarial_passed must be TRUE for deploy eligibility
- organization_id index mandatory for org-scoped queries

Mirrors migrations 0002 (table + uq_evaluation_runs_run_id +
ck_evaluation_runs_faithfulness_nonneg + ck_evaluation_runs_status),
0003 (indexes, incl. unique run_id index + GIN on the JSONB columns),
0009 (adds 'failed' to ck_evaluation_runs_status -- the workflow-exception
path was never a representable terminal status until this migration), and
0010 (adds agent_execution_metadata JSONB -- node-level status/timing,
Observer signals, Improver's full variant candidate set, and adversarial
per-question failure detail, all previously computed then discarded --
see verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.pipeline import Pipeline


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_evaluation_runs_run_id"),
        # Hard block: faithfulness < 0.5 is non-bypassable (enforced in service);
        # this CHECK only guards against negative scores at the DB boundary.
        CheckConstraint(
            "faithfulness IS NULL OR faithfulness >= 0",
            name="ck_evaluation_runs_faithfulness_nonneg",
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','blocked','failed')",
            name="ck_evaluation_runs_status",
        ),
        Index("ix_evaluation_runs_pipeline_id", "pipeline_id"),
        Index("ix_evaluation_runs_organization_id", "organization_id"),
        Index("ix_evaluation_runs_run_id", "run_id", unique=True),
        Index("ix_evaluation_runs_status", "status"),
        Index("ix_evaluation_runs_created_at", "created_at"),
        Index(
            "ix_evaluation_runs_org_pipeline", "organization_id", "pipeline_id"
        ),
        Index(
            "ix_evaluation_runs_ragas_metrics_gin",
            "ragas_metrics",
            postgresql_using="gin",
        ),
        Index(
            "ix_evaluation_runs_failure_taxonomy_gin",
            "failure_taxonomy",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # Correlation ID shared with the LangGraph run (caller-supplied; uuid7
    # default is a safety net only).
    run_id: Mapped[uuid.UUID] = mapped_column(default=uuid7, nullable=False)

    # Unified Score components — Rule 50 formula:
    # 0.25*recall + 0.35*quality + 0.25*faithfulness - 0.10*latency - 0.05*cost
    unified_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    recall: Mapped[float | None] = mapped_column(
        Numeric(4, 3), nullable=True
    )  # >= 0.85 required
    quality: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    faithfulness: Mapped[float | None] = mapped_column(
        Numeric(4, 3), nullable=True
    )  # < 0.5 = hard block
    latency_p95_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # < 3000 required
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Adversarial gate — must be TRUE for deploy eligibility
    adversarial_passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # RAGAS + failure details (JSONB)
    ragas_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"context_precision": 0.9, "context_recall": 0.85, "faithfulness": 0.72}
    # JSONB is genuinely heterogeneous here: score.py's API boundary treats it as
    # a list of failure-category codes, while improve.py/diagnose.py/the eval
    # workflow-failure path store scratch dicts (variant_config, error_type, ...).
    failure_taxonomy: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    # e.g. ["F-01", "F-03"] — from Diagnoser Agent

    # Real per-run data that was computed by nodes but previously discarded --
    # added 0010 (12-Jul-2026), see METRICS_WIRING_MATRIX.md. Single JSONB
    # column (not one column per concern) to avoid schema bloat; shape:
    # {
    #   "node_trace": [...],          # from GraphState.execution_trace verbatim
    #   "observer_signals": {...},    # error_rate, quality_trend, alert_triggered, observation_flags
    #   "improver_candidates": [...], # all 3 scored variants, not just the winner
    #   "adversarial_failures": [...] # per-question failure detail from the adversarial benchmark
    # }
    agent_execution_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
        # values: pending | running | completed | blocked
    )
    dataset_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

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

    # Relationships
    pipeline: Mapped[Pipeline] = relationship(back_populates="evaluation_runs")
    deployment: Mapped[Deployment | None] = relationship(
        back_populates="evaluation_run"
    )

    @property
    def is_deploy_eligible(self) -> bool:
        """True only when all 3 gates pass."""
        if self.faithfulness is not None and self.faithfulness < 0.5:
            return False  # hard block — non-bypassable
        if not self.adversarial_passed:
            return False
        return (self.unified_score or 0.0) >= 0.85

    def __repr__(self) -> str:
        return f"<EvaluationRun run={self.run_id} score={self.unified_score} eligible={self.is_deploy_eligible}>"
