"""Service -- golden dataset / version / question business rules.

Thin business-rule layer over EvaluationDatasetRepository: name validation,
lifecycle transitions, and version-publishing (which enforces the
never-mutate-a-past-version principle -- Rule 55). No LLM calls, no graph
dispatch -- that's batch_eval_service.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EvaluationDatasetNotFoundError
from app.models.evaluation_dataset import (
    EvaluationDataset,
    EvaluationDatasetVersion,
    GoldenQuestion,
)
from app.repositories.batch_evaluation_repository import BatchEvaluationRepository
from app.repositories.evaluation_dataset_repository import EvaluationDatasetRepository


class EvaluationDatasetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = EvaluationDatasetRepository(db)
        self._batch_repo = BatchEvaluationRepository(db)

    # ── Datasets ─────────────────────────────────────────────────────────────

    async def create_dataset(
        self,
        *,
        organization_id: str,
        name: str,
        description: str | None,
        domain: str | None,
        tags: list[str] | None,
        created_by: str,
    ) -> tuple[EvaluationDataset, EvaluationDatasetVersion]:
        """Creates the dataset AND its first version ('v1', draft) in one call
        -- a dataset with zero versions can't hold any golden questions
        (they FK to a version, not the dataset), so a bare dataset row alone
        would be a dead-end in the UI."""
        dataset = await self._repo.create_dataset(
            organization_id=uuid.UUID(organization_id),
            name=name,
            description=description,
            domain=domain,
            tags=tags,
            created_by=uuid.UUID(created_by),
        )
        version = await self._repo.create_version(
            dataset_id=dataset.id,
            organization_id=uuid.UUID(organization_id),
            version_label="v1",
            lifecycle_status="draft",
            created_by=uuid.UUID(created_by),
        )
        await self.db.commit()
        return dataset, version

    async def get_dataset(self, *, dataset_id: str, organization_id: str) -> EvaluationDataset:
        dataset = await self._repo.get_dataset_by_id(
            dataset_id=uuid.UUID(dataset_id), organization_id=uuid.UUID(organization_id)
        )
        if dataset is None:
            raise EvaluationDatasetNotFoundError(f"Dataset {dataset_id} not found")
        return dataset

    async def list_datasets(
        self, *, organization_id: str, status: str | None = None
    ) -> Sequence[EvaluationDataset]:
        return await self._repo.list_datasets(
            organization_id=uuid.UUID(organization_id), status=status
        )

    async def archive_dataset(self, *, dataset_id: str, organization_id: str) -> None:
        await self._repo.update_dataset(
            dataset_id=uuid.UUID(dataset_id),
            organization_id=uuid.UUID(organization_id),
            status="archived",
        )
        await self.db.commit()

    async def delete_dataset(self, *, dataset_id: str, organization_id: str) -> None:
        await self._repo.soft_delete_dataset(
            dataset_id=uuid.UUID(dataset_id), organization_id=uuid.UUID(organization_id)
        )
        await self.db.commit()

    # ── Versions ─────────────────────────────────────────────────────────────

    async def list_versions(
        self, *, dataset_id: str, organization_id: str
    ) -> Sequence[EvaluationDatasetVersion]:
        return await self._repo.list_versions(
            dataset_id=uuid.UUID(dataset_id), organization_id=uuid.UUID(organization_id)
        )

    async def publish_new_version(
        self,
        *,
        dataset_id: str,
        organization_id: str,
        notes: str | None,
        created_by: str,
        copy_from_latest: bool = True,
    ) -> EvaluationDatasetVersion:
        """Creates a new version row and, by default, clones every question
        from the current latest version into it -- this is what makes
        'v1 / v2 / v3' real: editing questions after this call only affects
        the NEW version's rows, never the one just published (or any earlier
        one), so past batch_runs.dataset_version_id references stay
        reproducible."""
        latest = await self._repo.get_latest_version(
            dataset_id=uuid.UUID(dataset_id), organization_id=uuid.UUID(organization_id)
        )
        next_label = f"v{len(await self._repo.list_versions(dataset_id=uuid.UUID(dataset_id), organization_id=uuid.UUID(organization_id))) + 1}"
        new_version = await self._repo.create_version(
            dataset_id=uuid.UUID(dataset_id),
            organization_id=uuid.UUID(organization_id),
            version_label=next_label,
            notes=notes,
            lifecycle_status="draft",
            created_by=uuid.UUID(created_by),
        )
        if copy_from_latest and latest is not None:
            await self._repo.copy_questions_to_new_version(
                source_version_id=latest.id,
                target_version_id=new_version.id,
                organization_id=uuid.UUID(organization_id),
            )
        await self.db.commit()
        return new_version

    async def set_version_status(
        self, *, version_id: str, organization_id: str, lifecycle_status: str
    ) -> None:
        await self._repo.set_version_lifecycle_status(
            version_id=uuid.UUID(version_id),
            organization_id=uuid.UUID(organization_id),
            lifecycle_status=lifecycle_status,
        )
        await self.db.commit()

    # ── Golden Questions ─────────────────────────────────────────────────────

    async def create_question(self, *, organization_id: str, **fields: Any) -> GoldenQuestion:  # noqa: ANN401
        dataset_version_id = fields.pop("dataset_version_id")
        ref_doc_id = fields.pop("reference_document_id", None)
        q = await self._repo.create_question(
            dataset_version_id=uuid.UUID(dataset_version_id),
            organization_id=uuid.UUID(organization_id),
            reference_document_id=uuid.UUID(ref_doc_id) if ref_doc_id else None,
            **fields,
        )
        await self.db.commit()
        return q

    async def list_questions(self, *, dataset_version_id: str, organization_id: str, **filters: Any) -> Any:  # noqa: ANN401
        return await self._repo.list_questions(
            dataset_version_id=uuid.UUID(dataset_version_id),
            organization_id=uuid.UUID(organization_id),
            **filters,
        )

    async def update_question(self, *, question_id: str, organization_id: str, **fields: Any) -> None:  # noqa: ANN401
        await self._repo.update_question(
            question_id=uuid.UUID(question_id),
            organization_id=uuid.UUID(organization_id),
            **fields,
        )
        await self.db.commit()

    async def review_question(
        self,
        *,
        question_id: str,
        organization_id: str,
        review_status: str,
        reviewer_id: str,
        reviewer_notes: str | None = None,
    ) -> None:
        await self._repo.set_review(
            question_id=uuid.UUID(question_id),
            organization_id=uuid.UUID(organization_id),
            review_status=review_status,
            reviewer_id=uuid.UUID(reviewer_id),
            reviewer_notes=reviewer_notes,
        )
        await self.db.commit()

    # ── Statistics ───────────────────────────────────────────────────────────

    async def get_dataset_statistics(self, *, dataset_id: str, organization_id: str) -> dict:
        """Question counts by review status for the latest version, plus the
        most recent batch run's average score for THIS dataset (across all
        its versions). A read/aggregate over existing tables -- no new
        capture, per the approved plan."""
        org_uuid = uuid.UUID(organization_id)
        latest = await self._repo.get_latest_version(
            dataset_id=uuid.UUID(dataset_id), organization_id=org_uuid
        )
        if latest is None:
            return {"question_counts": {}, "last_batch_run": None}

        question_counts = await self._repo.count_questions_by_review_status(
            dataset_version_id=latest.id, organization_id=org_uuid
        )
        recent_runs = await self._batch_repo.list_batch_runs(
            organization_id=org_uuid, dataset_id=uuid.UUID(dataset_id), limit=1
        )
        last_run_summary = None
        if recent_runs:
            last_run_summary = await self._batch_repo.get_batch_run_summary(
                batch_run_id=recent_runs[0].id, organization_id=org_uuid
            )
        return {
            "question_counts": question_counts,
            "latest_version_label": latest.version_label,
            "last_batch_run": last_run_summary,
        }
