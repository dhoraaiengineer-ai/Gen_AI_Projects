"""Integration tests for the Evaluation Center's golden-dataset layer --
real Supabase PostgreSQL, no DB mocking (Rule 80).

Covers EvaluationDatasetRepository/Service (dataset/version/question CRUD,
publish-new-version immutability) and BatchEvaluationRepository/
BatchEvalService's start_batch_run validation + pending-row bookkeeping.

dispatch_batch_run itself (the part that calls run_and_persist_evaluation,
which needs a real LLM/embedding call) is intentionally NOT exercised here --
same scoping decision as test_apply_improvement.py's docstring: that dispatch
path reuses the pre-existing, already-covered evaluation_dispatch logic, so
it isn't newly at risk from this feature. What IS newly at risk -- and what
these tests cover -- is the golden-dataset data model, version immutability,
and the pre-dispatch validation/bookkeeping this feature adds.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatasetVersionNotPublishedError, EmptyDatasetVersionError
from app.repositories.batch_evaluation_repository import BatchEvaluationRepository
from app.repositories.evaluation_dataset_repository import EvaluationDatasetRepository
from app.services.evaluation.batch_eval_service import BatchEvalService
from app.services.evaluation.evaluation_dataset_service import EvaluationDatasetService
from app.services.pipeline_service import PipelineService


async def _seed_organization(db_session: AsyncSession) -> uuid.UUID:
    org_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": str(org_id), "name": f"Test Org {org_id}", "slug": f"test-org-{org_id}"},
    )
    return org_id


async def _seed_user(db_session: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, organization_id, email, role) "
            "VALUES (:id, :org_id, :email, 'admin')"
        ),
        {"id": str(user_id), "org_id": str(org_id), "email": f"{user_id}@test.local"},
    )
    return user_id


async def _seed_pipeline(db_session: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    svc = PipelineService(db_session)
    pipeline = await svc.create(
        name=f"pipe-{uuid.uuid4()}",
        config_yaml=None,
        organization_id=str(org_id),
        x_trace_id="test-trace",
        chunk_strategy="semantic",
    )
    return uuid.UUID(pipeline["id"])


@pytest.mark.asyncio
class TestEvaluationDatasetRepository:
    async def test_create_dataset_creates_v1_draft_version(self, db_session: AsyncSession) -> None:
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        svc = EvaluationDatasetService(db_session)

        dataset, version = await svc.create_dataset(
            organization_id=str(org_id),
            name="Finance Benchmark",
            description="QA over annual reports",
            domain="finance",
            tags=["finance", "annual-report"],
            created_by=str(user_id),
        )

        assert dataset.name == "Finance Benchmark"
        assert version.version_label == "v1"
        assert version.lifecycle_status == "draft"
        assert version.dataset_id == dataset.id

    async def test_publish_new_version_never_mutates_the_previous_version(
        self, db_session: AsyncSession
    ) -> None:
        """The core immutability guarantee (Rule 55): editing questions after
        publish-new-version only affects the NEW version's rows."""
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        svc = EvaluationDatasetService(db_session)
        repo = EvaluationDatasetRepository(db_session)

        dataset, v1 = await svc.create_dataset(
            organization_id=str(org_id),
            name="Legal Benchmark",
            description=None,
            domain=None,
            tags=None,
            created_by=str(user_id),
        )
        q1 = await repo.create_question(
            dataset_version_id=v1.id,
            organization_id=org_id,
            question="What is the termination clause?",
            reference_answer="30 days notice.",
        )
        await db_session.commit()

        v2 = await svc.publish_new_version(
            dataset_id=str(dataset.id),
            organization_id=str(org_id),
            notes="Added clarifying answer",
            created_by=str(user_id),
            copy_from_latest=True,
        )
        assert v2.version_label == "v2"

        v2_questions = await repo.list_questions(
            dataset_version_id=v2.id, organization_id=org_id
        )
        assert len(v2_questions) == 1
        v2_question = v2_questions[0]
        assert v2_question.id != q1.id  # a real clone, not a re-pointed FK
        assert v2_question.question == q1.question

        # Edit the clone -- must NOT affect v1's row.
        await repo.update_question(
            question_id=v2_question.id,
            organization_id=org_id,
            reference_answer="30 days written notice, per Section 4.2.",
        )
        await db_session.commit()

        v1_question_reloaded = await repo.get_question_by_id(
            question_id=q1.id, organization_id=org_id
        )
        assert v1_question_reloaded is not None
        assert v1_question_reloaded.reference_answer == "30 days notice."

    async def test_review_workflow_records_reviewer_and_timestamp(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        reviewer_id = await _seed_user(db_session, org_id)
        svc = EvaluationDatasetService(db_session)
        repo = EvaluationDatasetRepository(db_session)

        dataset, v1 = await svc.create_dataset(
            organization_id=str(org_id),
            name="Ops Benchmark",
            description=None,
            domain=None,
            tags=None,
            created_by=str(user_id),
        )
        q = await repo.create_question(
            dataset_version_id=v1.id,
            organization_id=org_id,
            question="What is the SLA for P1 incidents?",
        )
        await db_session.commit()
        assert q.review_status == "draft"

        await svc.review_question(
            question_id=str(q.id),
            organization_id=str(org_id),
            review_status="approved",
            reviewer_id=str(reviewer_id),
            reviewer_notes="Looks good.",
        )

        reloaded = await repo.get_question_by_id(question_id=q.id, organization_id=org_id)
        assert reloaded is not None
        assert reloaded.review_status == "approved"
        assert reloaded.reviewer_id == reviewer_id
        assert reloaded.reviewed_at is not None


@pytest.mark.asyncio
class TestBatchEvalServiceStartBatchRun:
    async def test_rejects_a_batch_run_against_a_draft_version(
        self, db_session: AsyncSession
    ) -> None:
        """Only 'published' versions are selectable -- enforced with a real
        422-mapped exception, not silently allowed."""
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        pipeline_id = await _seed_pipeline(db_session, org_id)
        dataset_svc = EvaluationDatasetService(db_session)
        batch_svc = BatchEvalService(db_session)

        _, v1 = await dataset_svc.create_dataset(
            organization_id=str(org_id),
            name="Draft Benchmark",
            description=None,
            domain=None,
            tags=None,
            created_by=str(user_id),
        )
        assert v1.lifecycle_status == "draft"

        with pytest.raises(DatasetVersionNotPublishedError):
            await batch_svc.start_batch_run(
                dataset_version_id=str(v1.id),
                pipeline_id=str(pipeline_id),
                config_id=None,
                organization_id=str(org_id),
                user_id=str(user_id),
                x_trace_id="test-trace",
                app_state=object(),
            )

    async def test_rejects_a_published_version_with_no_approved_questions(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        pipeline_id = await _seed_pipeline(db_session, org_id)
        dataset_svc = EvaluationDatasetService(db_session)
        batch_svc = BatchEvalService(db_session)
        dataset_repo = EvaluationDatasetRepository(db_session)

        _, v1 = await dataset_svc.create_dataset(
            organization_id=str(org_id),
            name="Empty Benchmark",
            description=None,
            domain=None,
            tags=None,
            created_by=str(user_id),
        )
        # A question exists but is still 'draft' -- not 'approved' -- so the
        # published version still has zero DISPATCHABLE questions.
        await dataset_repo.create_question(
            dataset_version_id=v1.id, organization_id=org_id, question="Unreviewed question?"
        )
        await dataset_svc.set_version_status(
            version_id=str(v1.id), organization_id=str(org_id), lifecycle_status="published"
        )

        with pytest.raises(EmptyDatasetVersionError):
            await batch_svc.start_batch_run(
                dataset_version_id=str(v1.id),
                pipeline_id=str(pipeline_id),
                config_id=None,
                organization_id=str(org_id),
                user_id=str(user_id),
                x_trace_id="test-trace",
                app_state=object(),
            )

    async def test_creates_one_pending_row_per_approved_question(
        self, db_session: AsyncSession
    ) -> None:
        """The resumability mechanism: start_batch_run bulk-inserts one
        'pending' batch_evaluations row per approved question up front,
        before any dispatch happens."""
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        pipeline_id = await _seed_pipeline(db_session, org_id)
        dataset_svc = EvaluationDatasetService(db_session)
        batch_svc = BatchEvalService(db_session)
        dataset_repo = EvaluationDatasetRepository(db_session)
        batch_repo = BatchEvaluationRepository(db_session)

        _, v1 = await dataset_svc.create_dataset(
            organization_id=str(org_id),
            name="Ready Benchmark",
            description=None,
            domain=None,
            tags=None,
            created_by=str(user_id),
        )
        approved_ids = []
        for i in range(3):
            q = await dataset_repo.create_question(
                dataset_version_id=v1.id,
                organization_id=org_id,
                question=f"Question {i}?",
                reference_answer=f"Answer {i}.",
            )
            await dataset_svc.review_question(
                question_id=str(q.id),
                organization_id=str(org_id),
                review_status="approved",
                reviewer_id=str(user_id),
            )
            approved_ids.append(q.id)
        # A rejected question must NOT be dispatched.
        rejected = await dataset_repo.create_question(
            dataset_version_id=v1.id, organization_id=org_id, question="Bad question?"
        )
        await dataset_svc.review_question(
            question_id=str(rejected.id),
            organization_id=str(org_id),
            review_status="rejected",
            reviewer_id=str(user_id),
        )
        await dataset_svc.set_version_status(
            version_id=str(v1.id), organization_id=str(org_id), lifecycle_status="published"
        )

        batch_run = await batch_svc.start_batch_run(
            dataset_version_id=str(v1.id),
            pipeline_id=str(pipeline_id),
            config_id=None,
            organization_id=str(org_id),
            user_id=str(user_id),
            x_trace_id="test-trace",
            app_state=object(),
        )
        assert batch_run.status == "queued"

        rows = await batch_repo.list_by_batch_run(
            batch_run_id=batch_run.id, organization_id=org_id
        )
        assert len(rows) == 3  # not 4 -- the rejected question was excluded
        assert {r.golden_question_id for r in rows} == set(approved_ids)
        assert all(r.status == "pending" for r in rows)

    async def test_cancel_only_touches_pending_rows_not_running_ones(
        self, db_session: AsyncSession
    ) -> None:
        """deployment-policies.md Rule 8/10: cancellation never kills an
        in-flight graph invocation -- only 'pending' rows are marked failed."""
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, org_id)
        pipeline_id = await _seed_pipeline(db_session, org_id)
        dataset_svc = EvaluationDatasetService(db_session)
        batch_svc = BatchEvalService(db_session)
        dataset_repo = EvaluationDatasetRepository(db_session)
        batch_repo = BatchEvaluationRepository(db_session)

        _, v1 = await dataset_svc.create_dataset(
            organization_id=str(org_id),
            name="Cancel Benchmark",
            description=None,
            domain=None,
            tags=None,
            created_by=str(user_id),
        )
        for i in range(2):
            q = await dataset_repo.create_question(
                dataset_version_id=v1.id, organization_id=org_id, question=f"Q{i}?"
            )
            await dataset_svc.review_question(
                question_id=str(q.id),
                organization_id=str(org_id),
                review_status="approved",
                reviewer_id=str(user_id),
            )
        await dataset_svc.set_version_status(
            version_id=str(v1.id), organization_id=str(org_id), lifecycle_status="published"
        )

        batch_run = await batch_svc.start_batch_run(
            dataset_version_id=str(v1.id),
            pipeline_id=str(pipeline_id),
            config_id=None,
            organization_id=str(org_id),
            user_id=str(user_id),
            x_trace_id="test-trace",
            app_state=object(),
        )
        rows = await batch_repo.list_by_batch_run(
            batch_run_id=batch_run.id, organization_id=org_id
        )
        running_row, pending_row = rows[0], rows[1]
        await batch_repo.mark_running(
            batch_evaluation_id=running_row.id, organization_id=org_id
        )
        await db_session.commit()

        await batch_svc.cancel_batch_run(
            batch_run_id=str(batch_run.id), organization_id=str(org_id)
        )

        reloaded_running = await batch_repo.get_by_id(
            batch_evaluation_id=running_row.id, organization_id=org_id
        )
        reloaded_pending = await batch_repo.get_by_id(
            batch_evaluation_id=pending_row.id, organization_id=org_id
        )
        assert reloaded_running is not None
        assert reloaded_running.status == "running"  # untouched -- left to finish
        assert reloaded_pending is not None
        assert reloaded_pending.status == "failed"  # cancelled before dispatch

        reloaded_batch_run = await batch_repo.get_batch_run(
            batch_run_id=batch_run.id, organization_id=org_id
        )
        assert reloaded_batch_run is not None
        assert reloaded_batch_run.status == "cancelled"
