"""ORM model -- evaluation_configs table.

Rows are never updated after creation (Rule 55: immutable, reproducible
config). An "edit" in the UI creates a new row -- batch_runs.config_id
always points to the exact config a run actually used. Mirrors migration
0017.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class EvaluationConfig(Base):
    __tablename__ = "evaluation_configs"
    __table_args__ = (
        Index("ix_evaluation_configs_organization_id", "organization_id"),
        Index("ix_evaluation_configs_pipeline_id", "pipeline_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    retriever_strategy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reranker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    top_k: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    chunk_size: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # judge_provider/judge_model: which entry of AutoRAG's real provider chain
    # (Gemini Flash 3.5 -> KiMi K2.6 -> Gemini 3.5, resolve_chat_provider_chain()
    # in app/core/config.py) a batch run's RAGAS judging should prefer -- NOT a
    # separate, unconfigured provider. Nullable: falls back to the pipeline's
    # normal chain when unset.
    judge_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    judge_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<EvaluationConfig name={self.name} pipeline_id={self.pipeline_id}>"
