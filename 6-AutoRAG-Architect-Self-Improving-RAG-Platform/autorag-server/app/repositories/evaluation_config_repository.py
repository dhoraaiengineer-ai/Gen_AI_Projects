"""Repository -- evaluation_configs table.

Rows are immutable once created (Rule 55) -- there is no update_config
method; "editing" a config in the UI calls create_config again with a new
name, so past batch_runs.config_id references stay reproducible.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_config import EvaluationConfig


class EvaluationConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_config(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        pipeline_id: uuid.UUID | None = None,
        retriever_strategy: str | None = None,
        reranker: str | None = None,
        embedding_model: str | None = None,
        top_k: int | None = None,
        chunk_size: int | None = None,
        judge_provider: str | None = None,
        judge_model: str | None = None,
        temperature: float | None = None,
        created_by: uuid.UUID | None = None,
    ) -> EvaluationConfig:
        config = EvaluationConfig(
            organization_id=organization_id,
            pipeline_id=pipeline_id,
            name=name,
            retriever_strategy=retriever_strategy,
            reranker=reranker,
            embedding_model=embedding_model,
            top_k=top_k,
            chunk_size=chunk_size,
            judge_provider=judge_provider,
            judge_model=judge_model,
            temperature=temperature,
            created_by=created_by,
        )
        self._session.add(config)
        await self._session.flush()
        await self._session.refresh(config)
        return config

    async def get_by_id(
        self, *, config_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationConfig | None:
        stmt = select(EvaluationConfig).where(
            EvaluationConfig.id == config_id,
            EvaluationConfig.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_configs(
        self,
        *,
        organization_id: uuid.UUID,
        pipeline_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationConfig]:
        stmt = (
            select(EvaluationConfig)
            .where(EvaluationConfig.organization_id == organization_id)
            .order_by(EvaluationConfig.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if pipeline_id is not None:
            stmt = stmt.where(EvaluationConfig.pipeline_id == pipeline_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()
