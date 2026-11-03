"""Repository — pipeline_versions table.

All DB access for pipeline_versions. No business logic — pure persistence.
Immutable rows (no update methods) -- one row per (pipeline_id, version_number),
matching the model's own "Immutable after creation" contract
(app/models/pipeline_version.py).

Pattern mirrors pipeline_repository.py: every query is organization_id-scoped
(Rule 30 multi-tenancy).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_version import PipelineVersion


class PipelineVersionRepository:
    """Data-access layer for pipeline_versions table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
        version_number: int,
        vector_table_name: str,
        chunk_strategy: str,
        embedding_model: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        retrieval_k: int | None = None,
        config_snapshot: dict | None = None,
    ) -> PipelineVersion:
        """Insert an immutable pipeline_versions row and return the ORM instance."""
        version = PipelineVersion(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            version_number=version_number,
            vector_table_name=vector_table_name,
            chunk_strategy=chunk_strategy,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            retrieval_k=retrieval_k,
            config_snapshot=config_snapshot,
        )
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_by_pipeline_and_version(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
        version_number: int,
    ) -> PipelineVersion | None:
        """Fetch a single version row -- used to resolve a pipeline's active config
        (config_snapshot of the row matching pipelines.current_version)."""
        stmt = select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline_id,
            PipelineVersion.organization_id == organization_id,
            PipelineVersion.version_number == version_number,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Sequence[PipelineVersion]:
        """List all versions for a pipeline, oldest first -- feeds the version
        history / optimization timeline (GET /pipelines/{id}/versions)."""
        stmt = (
            select(PipelineVersion)
            .where(
                PipelineVersion.pipeline_id == pipeline_id,
                PipelineVersion.organization_id == organization_id,
            )
            .order_by(PipelineVersion.version_number.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
