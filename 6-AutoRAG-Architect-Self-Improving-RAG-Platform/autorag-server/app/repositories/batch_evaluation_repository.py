"""Repository -- batch_runs (header) and batch_evaluations (per-question ledger).

Resume mechanism: create_pending_rows bulk-inserts one 'pending' row per
golden question before dispatch; list_pending_or_failed is what
batch_eval_service.resume_batch_run re-queries to only re-dispatch
incomplete work after an interruption.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Float, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch_evaluation import BatchEvaluation, BatchRun
from app.models.evaluation_dataset import EvaluationDatasetVersion
from app.models.evaluation_run import EvaluationRun


class BatchEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── batch_runs (header) ─────────────────────────────────────────────────

    async def create_batch_run(
        self,
        *,
        organization_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        pipeline_id: uuid.UUID,
        config_id: uuid.UUID | None,
        created_by: uuid.UUID | None,
    ) -> BatchRun:
        run = BatchRun(
            organization_id=organization_id,
            dataset_version_id=dataset_version_id,
            pipeline_id=pipeline_id,
            config_id=config_id,
            created_by=created_by,
            status="queued",
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def get_batch_run(
        self, *, batch_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> BatchRun | None:
        stmt = select(BatchRun).where(
            BatchRun.id == batch_run_id, BatchRun.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_batch_runs(
        self,
        *,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
        pipeline_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[BatchRun]:
        stmt = select(BatchRun).where(BatchRun.organization_id == organization_id)
        if dataset_id is not None:
            # batch_runs only stores dataset_version_id -- join through
            # evaluation_dataset_versions to filter by the parent dataset.
            stmt = stmt.join(
                EvaluationDatasetVersion, EvaluationDatasetVersion.id == BatchRun.dataset_version_id
            ).where(EvaluationDatasetVersion.dataset_id == dataset_id)
        if pipeline_id is not None:
            stmt = stmt.where(BatchRun.pipeline_id == pipeline_id)
        if status is not None:
            stmt = stmt.where(BatchRun.status == status)
        stmt = stmt.order_by(BatchRun.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def set_batch_run_status(
        self,
        *,
        batch_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        cancelled_at: datetime | None = None,
    ) -> None:
        values: dict = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if cancelled_at is not None:
            values["cancelled_at"] = cancelled_at
        stmt = (
            update(BatchRun)
            .where(BatchRun.id == batch_run_id, BatchRun.organization_id == organization_id)
            .values(**values)
        )
        await self._session.execute(stmt)

    # ── batch_evaluations (per-question ledger) ─────────────────────────────

    async def create_pending_rows(
        self,
        *,
        batch_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        pipeline_id: uuid.UUID,
        config_id: uuid.UUID | None,
        golden_question_ids: list[uuid.UUID],
    ) -> list[BatchEvaluation]:
        """Bulk-insert one 'pending' row per question, up front -- this is
        what makes resume-after-interruption possible: any row still
        'pending' after a crash was never dispatched."""
        rows = [
            BatchEvaluation(
                batch_run_id=batch_run_id,
                organization_id=organization_id,
                dataset_version_id=dataset_version_id,
                golden_question_id=qid,
                pipeline_id=pipeline_id,
                config_id=config_id,
                status="pending",
            )
            for qid in golden_question_ids
        ]
        self._session.add_all(rows)
        await self._session.flush()
        for row in rows:
            await self._session.refresh(row)
        return rows

    async def get_by_id(
        self, *, batch_evaluation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> BatchEvaluation | None:
        stmt = select(BatchEvaluation).where(
            BatchEvaluation.id == batch_evaluation_id,
            BatchEvaluation.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_batch_run(
        self,
        *,
        batch_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str | None = None,
        review_status: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> Sequence[BatchEvaluation]:
        stmt = select(BatchEvaluation).where(
            BatchEvaluation.batch_run_id == batch_run_id,
            BatchEvaluation.organization_id == organization_id,
        )
        if status is not None:
            stmt = stmt.where(BatchEvaluation.status == status)
        if review_status is not None:
            stmt = stmt.where(BatchEvaluation.review_status == review_status)
        stmt = stmt.order_by(BatchEvaluation.created_at.asc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_pending_or_failed(
        self, *, batch_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Sequence[BatchEvaluation]:
        """Resume query -- rows this batch run still needs to (re)dispatch."""
        stmt = select(BatchEvaluation).where(
            BatchEvaluation.batch_run_id == batch_run_id,
            BatchEvaluation.organization_id == organization_id,
            BatchEvaluation.status.in_(["pending", "failed"]),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_running(
        self, *, batch_evaluation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        stmt = (
            update(BatchEvaluation)
            .where(
                BatchEvaluation.id == batch_evaluation_id,
                BatchEvaluation.organization_id == organization_id,
            )
            .values(status="running", updated_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def mark_completed(
        self,
        *,
        batch_evaluation_id: uuid.UUID,
        organization_id: uuid.UUID,
        evaluation_run_id: uuid.UUID,
    ) -> None:
        stmt = (
            update(BatchEvaluation)
            .where(
                BatchEvaluation.id == batch_evaluation_id,
                BatchEvaluation.organization_id == organization_id,
            )
            .values(
                status="completed",
                evaluation_run_id=evaluation_run_id,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def mark_failed(
        self,
        *,
        batch_evaluation_id: uuid.UUID,
        organization_id: uuid.UUID,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """V4 (26-Jul-2026): error_message/error_type are optional so existing
        call sites that genuinely have no exception to report (e.g. the
        golden question itself was deleted mid-run) still work -- but every
        real dispatch-failure call site now passes a real message, never a
        fabricated one."""
        now = datetime.now(UTC)
        values: dict = {"status": "failed", "updated_at": now}
        if error_message is not None:
            values["error_message"] = error_message
            values["failed_at"] = now
        if error_type is not None:
            values["error_type"] = error_type
        stmt = (
            update(BatchEvaluation)
            .where(
                BatchEvaluation.id == batch_evaluation_id,
                BatchEvaluation.organization_id == organization_id,
            )
            .values(**values)
        )
        await self._session.execute(stmt)

    async def cancel_pending_rows(
        self, *, batch_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        """Cancellation semantics (deployment-policies.md Rule 8/10): only
        'pending' rows are touched -- an already-'running' row is left to
        finish, never killed mid-flight."""
        stmt = (
            update(BatchEvaluation)
            .where(
                BatchEvaluation.batch_run_id == batch_run_id,
                BatchEvaluation.organization_id == organization_id,
                BatchEvaluation.status == "pending",
            )
            .values(status="failed", updated_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    # ── Human review ─────────────────────────────────────────────────────────

    async def set_review(
        self,
        *,
        batch_evaluation_id: uuid.UUID,
        organization_id: uuid.UUID,
        review_status: str,
        reviewer_id: uuid.UUID | None,
        reviewer_notes: str | None = None,
        corrected_answer: str | None = None,
    ) -> None:
        """Reviews a batch run's per-question RESULT -- never mutates
        evaluation_run_id or any score column, only the review fields."""
        stmt = (
            update(BatchEvaluation)
            .where(
                BatchEvaluation.id == batch_evaluation_id,
                BatchEvaluation.organization_id == organization_id,
            )
            .values(
                review_status=review_status,
                reviewer_id=reviewer_id,
                reviewer_notes=reviewer_notes,
                corrected_answer=corrected_answer,
                reviewed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    # ── Result detail / aggregation ─────────────────────────────────────────

    async def get_with_evaluation_run(
        self, *, batch_evaluation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> tuple[BatchEvaluation, EvaluationRun | None] | None:
        """Result Detail inspector's data source -- joins to the underlying
        evaluation_runs row for ragas_metrics/agent_execution_metadata."""
        row = await self.get_by_id(
            batch_evaluation_id=batch_evaluation_id, organization_id=organization_id
        )
        if row is None:
            return None
        if row.evaluation_run_id is None:
            return row, None
        stmt = select(EvaluationRun).where(
            EvaluationRun.id == row.evaluation_run_id,
            EvaluationRun.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return row, result.scalar_one_or_none()

    async def get_batch_run_summary(
        self, *, batch_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> dict:
        """Aggregates batch_evaluations joined to evaluation_runs -- average
        score, pass/fail counts, worst-scoring questions. Feeds Overview,
        Batch Run detail, and the Failed Questions tab."""
        stmt = (
            select(
                BatchEvaluation.status,
                func.count(BatchEvaluation.id),
            )
            .where(
                BatchEvaluation.batch_run_id == batch_run_id,
                BatchEvaluation.organization_id == organization_id,
            )
            .group_by(BatchEvaluation.status)
        )
        result = await self._session.execute(stmt)
        counts_by_status: dict[str, int] = dict(result.tuples().all())

        score_stmt = (
            select(
                func.avg(EvaluationRun.unified_score),
                func.count(EvaluationRun.id).filter(EvaluationRun.unified_score < 0.70),
            )
            .select_from(BatchEvaluation)
            .join(EvaluationRun, EvaluationRun.id == BatchEvaluation.evaluation_run_id)
            .where(
                BatchEvaluation.batch_run_id == batch_run_id,
                BatchEvaluation.organization_id == organization_id,
            )
        )
        score_result = await self._session.execute(score_stmt)
        avg_score, low_score_count = score_result.one_or_none() or (None, 0)

        # V4 (26-Jul-2026): per-metric averages across the batch, extracted
        # from EvaluationRun.ragas_metrics (JSONB) -- powers the Evaluation
        # Results page's "Overall Metrics" row. Rows with no ragas_metrics key
        # for a given metric (e.g. answer_correctness with no ground truth)
        # are excluded from that metric's average by avg()'s NULL handling,
        # not silently counted as 0.
        metric_keys = [
            "faithfulness",
            "context_recall",
            "answer_relevancy",
            "context_precision",
            "answer_correctness",
        ]
        metrics_stmt = (
            select(
                *[
                    func.avg(cast(EvaluationRun.ragas_metrics[key].astext, Float)).label(key)
                    for key in metric_keys
                ]
            )
            .select_from(BatchEvaluation)
            .join(EvaluationRun, EvaluationRun.id == BatchEvaluation.evaluation_run_id)
            .where(
                BatchEvaluation.batch_run_id == batch_run_id,
                BatchEvaluation.organization_id == organization_id,
            )
        )
        metrics_result = await self._session.execute(metrics_stmt)
        metrics_row = metrics_result.one_or_none()
        metric_averages: dict[str, float | None] = {
            key: (float(value) if value is not None else None)
            for key, value in zip(metric_keys, metrics_row or (None,) * len(metric_keys), strict=True)
        }

        return {
            "counts_by_status": counts_by_status,
            "average_unified_score": float(avg_score) if avg_score is not None else None,
            "low_score_count": low_score_count or 0,
            "metric_averages": metric_averages,
        }

    async def get_worst_scoring(
        self, *, batch_run_id: uuid.UUID, organization_id: uuid.UUID, limit: int = 10
    ) -> Sequence[tuple[BatchEvaluation, EvaluationRun]]:
        stmt = (
            select(BatchEvaluation, EvaluationRun)
            .join(EvaluationRun, EvaluationRun.id == BatchEvaluation.evaluation_run_id)
            .where(
                BatchEvaluation.batch_run_id == batch_run_id,
                BatchEvaluation.organization_id == organization_id,
                EvaluationRun.unified_score.is_not(None),
            )
            .order_by(EvaluationRun.unified_score.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.all()  # type: ignore[return-value]
