"""Repository -- evaluation_datasets, evaluation_dataset_versions, golden_questions.

All DB access for the golden-dataset tables. No business logic -- pure
persistence operations only (validation like "name already exists" or
"cannot publish a version with zero questions" belongs in
evaluation_dataset_service.py).

All queries MUST include organization_id scoping (Rule 30).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_dataset import (
    EvaluationDataset,
    EvaluationDatasetVersion,
    GoldenQuestion,
)


class EvaluationDatasetRepository:
    """Data-access layer for evaluation_datasets and its child tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Datasets ─────────────────────────────────────────────────────────────

    async def create_dataset(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        description: str | None = None,
        domain: str | None = None,
        tags: list[str] | None = None,
        created_by: uuid.UUID | None = None,
    ) -> EvaluationDataset:
        dataset = EvaluationDataset(
            organization_id=organization_id,
            name=name,
            description=description,
            domain=domain,
            tags=tags,
            created_by=created_by,
        )
        self._session.add(dataset)
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def get_dataset_by_id(
        self, *, dataset_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationDataset | None:
        stmt = select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.organization_id == organization_id,
            EvaluationDataset.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_datasets(
        self,
        *,
        organization_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationDataset]:
        stmt = (
            select(EvaluationDataset)
            .where(
                EvaluationDataset.organization_id == organization_id,
                EvaluationDataset.deleted_at.is_(None),
            )
            .order_by(EvaluationDataset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(EvaluationDataset.status == status)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_dataset(
        self,
        *,
        dataset_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields: Any,  # noqa: ANN401
    ) -> None:
        values = {k: v for k, v in fields.items() if v is not None}
        values["updated_at"] = datetime.now(UTC)
        stmt = (
            update(EvaluationDataset)
            .where(
                EvaluationDataset.id == dataset_id,
                EvaluationDataset.organization_id == organization_id,
            )
            .values(**values)
        )
        await self._session.execute(stmt)

    async def soft_delete_dataset(
        self, *, dataset_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        stmt = (
            update(EvaluationDataset)
            .where(
                EvaluationDataset.id == dataset_id,
                EvaluationDataset.organization_id == organization_id,
            )
            .values(deleted_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    # ── Versions ─────────────────────────────────────────────────────────────

    async def create_version(
        self,
        *,
        dataset_id: uuid.UUID,
        organization_id: uuid.UUID,
        version_label: str,
        notes: str | None = None,
        lifecycle_status: str = "draft",
        created_by: uuid.UUID | None = None,
    ) -> EvaluationDatasetVersion:
        """Create a new, immutable dataset version row.

        Callers (evaluation_dataset_service.publish_new_version) are
        responsible for copying forward the previous version's questions if
        that's the desired behavior -- this method only creates the empty
        version shell.
        """
        version = EvaluationDatasetVersion(
            dataset_id=dataset_id,
            organization_id=organization_id,
            version_label=version_label,
            notes=notes,
            lifecycle_status=lifecycle_status,
            created_by=created_by,
        )
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_version_by_id(
        self, *, version_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationDatasetVersion | None:
        stmt = select(EvaluationDatasetVersion).where(
            EvaluationDatasetVersion.id == version_id,
            EvaluationDatasetVersion.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(
        self, *, dataset_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Sequence[EvaluationDatasetVersion]:
        """Newest first -- feeds the Version History timeline UI."""
        stmt = (
            select(EvaluationDatasetVersion)
            .where(
                EvaluationDatasetVersion.dataset_id == dataset_id,
                EvaluationDatasetVersion.organization_id == organization_id,
            )
            .order_by(EvaluationDatasetVersion.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_latest_version(
        self, *, dataset_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationDatasetVersion | None:
        stmt = (
            select(EvaluationDatasetVersion)
            .where(
                EvaluationDatasetVersion.dataset_id == dataset_id,
                EvaluationDatasetVersion.organization_id == organization_id,
            )
            .order_by(EvaluationDatasetVersion.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_version_lifecycle_status(
        self, *, version_id: uuid.UUID, organization_id: uuid.UUID, lifecycle_status: str
    ) -> None:
        stmt = (
            update(EvaluationDatasetVersion)
            .where(
                EvaluationDatasetVersion.id == version_id,
                EvaluationDatasetVersion.organization_id == organization_id,
            )
            .values(lifecycle_status=lifecycle_status)
        )
        await self._session.execute(stmt)

    # ── Golden Questions ─────────────────────────────────────────────────────

    async def create_question(
        self,
        *,
        dataset_version_id: uuid.UUID,
        organization_id: uuid.UUID,
        question: str,
        purpose: str | None = None,
        reference_answer: str | None = None,
        expected_context: str | None = None,
        reference_document_id: uuid.UUID | None = None,
        reference_pages: str | None = None,
        relevant_chunk_ids: list[str] | None = None,
        category: str | None = None,
        difficulty: str | None = None,
        metric_focus: str | None = None,
        tags: list[str] | None = None,
    ) -> GoldenQuestion:
        q = GoldenQuestion(
            dataset_version_id=dataset_version_id,
            organization_id=organization_id,
            question=question,
            purpose=purpose,
            reference_answer=reference_answer,
            expected_context=expected_context,
            reference_document_id=reference_document_id,
            reference_pages=reference_pages,
            relevant_chunk_ids=relevant_chunk_ids,
            category=category,
            difficulty=difficulty,
            metric_focus=metric_focus,
            tags=tags,
        )
        self._session.add(q)
        await self._session.flush()
        await self._session.refresh(q)
        return q

    async def get_question_by_id(
        self, *, question_id: uuid.UUID, organization_id: uuid.UUID
    ) -> GoldenQuestion | None:
        stmt = select(GoldenQuestion).where(
            GoldenQuestion.id == question_id,
            GoldenQuestion.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_questions(
        self,
        *,
        dataset_version_id: uuid.UUID,
        organization_id: uuid.UUID,
        review_status: str | None = None,
        category: str | None = None,
        difficulty: str | None = None,
        metric_focus: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[GoldenQuestion]:
        stmt = select(GoldenQuestion).where(
            GoldenQuestion.dataset_version_id == dataset_version_id,
            GoldenQuestion.organization_id == organization_id,
        )
        if review_status is not None:
            stmt = stmt.where(GoldenQuestion.review_status == review_status)
        if category is not None:
            stmt = stmt.where(GoldenQuestion.category == category)
        if difficulty is not None:
            stmt = stmt.where(GoldenQuestion.difficulty == difficulty)
        if metric_focus is not None:
            stmt = stmt.where(GoldenQuestion.metric_focus == metric_focus)
        if search:
            stmt = stmt.where(GoldenQuestion.question.ilike(f"%{search}%"))
        stmt = stmt.order_by(GoldenQuestion.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_published_questions(
        self, *, dataset_version_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Sequence[GoldenQuestion]:
        """Only approved questions -- what start_batch_run actually dispatches."""
        stmt = select(GoldenQuestion).where(
            GoldenQuestion.dataset_version_id == dataset_version_id,
            GoldenQuestion.organization_id == organization_id,
            GoldenQuestion.review_status == "approved",
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_question(
        self,
        *,
        question_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields: Any,  # noqa: ANN401
    ) -> None:
        values = {k: v for k, v in fields.items() if v is not None}
        values["updated_at"] = datetime.now(UTC)
        stmt = (
            update(GoldenQuestion)
            .where(
                GoldenQuestion.id == question_id,
                GoldenQuestion.organization_id == organization_id,
            )
            .values(**values)
        )
        await self._session.execute(stmt)

    async def set_review(
        self,
        *,
        question_id: uuid.UUID,
        organization_id: uuid.UUID,
        review_status: str,
        reviewer_id: uuid.UUID | None,
        reviewer_notes: str | None = None,
    ) -> None:
        stmt = (
            update(GoldenQuestion)
            .where(
                GoldenQuestion.id == question_id,
                GoldenQuestion.organization_id == organization_id,
            )
            .values(
                review_status=review_status,
                reviewer_id=reviewer_id,
                reviewer_notes=reviewer_notes,
                reviewed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def copy_questions_to_new_version(
        self, *, source_version_id: uuid.UUID, target_version_id: uuid.UUID, organization_id: uuid.UUID
    ) -> int:
        """Publish-new-version support: clone every question row from the
        source version into the target version. The source version's rows
        are untouched -- this is what makes a past version's benchmark
        results reproducible even after later edits (Rule 55)."""
        source_questions = await self.list_questions(
            dataset_version_id=source_version_id,
            organization_id=organization_id,
            limit=10_000,
        )
        for q in source_questions:
            clone = GoldenQuestion(
                dataset_version_id=target_version_id,
                organization_id=organization_id,
                question=q.question,
                reference_answer=q.reference_answer,
                expected_context=q.expected_context,
                reference_document_id=q.reference_document_id,
                reference_pages=q.reference_pages,
                relevant_chunk_ids=q.relevant_chunk_ids,
                category=q.category,
                difficulty=q.difficulty,
                metric_focus=q.metric_focus,
                tags=q.tags,
                review_status=q.review_status,
            )
            self._session.add(clone)
        await self._session.flush()
        return len(source_questions)

    # ── Statistics ───────────────────────────────────────────────────────────

    async def count_questions_by_review_status(
        self, *, dataset_version_id: uuid.UUID, organization_id: uuid.UUID
    ) -> dict[str, int]:
        stmt = (
            select(GoldenQuestion.review_status, func.count(GoldenQuestion.id))
            .where(
                GoldenQuestion.dataset_version_id == dataset_version_id,
                GoldenQuestion.organization_id == organization_id,
            )
            .group_by(GoldenQuestion.review_status)
        )
        result = await self._session.execute(stmt)
        return dict(result.tuples().all())
