"""Repository — experiment_runs table.

Table existed since migration 0002 (model: app/models/experiment_run.py,
"Improver Agent variants + MLflow tracking") but had no repository/service/
route ever built on it -- unused until the Apply Improvement feature
(20-Jul-2026), which repurposes it exactly per its own original design intent:
one row per applied Improver variant, tracking parent run, the config that
was applied, the resulting pipeline version, and the real (possibly worse,
never fabricated) score delta.

Pattern mirrors evaluation_repository.py: every query is organization_id-scoped
(Rule 30 multi-tenancy).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment_run import ExperimentRun


class ExperimentRunRepository:
    """Data-access layer for experiment_runs table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
        parent_evaluation_run_id: uuid.UUID | None,
        variant_config: dict,
        status: str = "pending",
        result_pipeline_version_id: uuid.UUID | None = None,
    ) -> ExperimentRun:
        """Insert a new experiment_runs row for a just-dispatched apply-improvement
        attempt. result_pipeline_version_id is known immediately (the version is
        created before this row, in prepare_apply_improvement); unified_score/
        score_delta/result_evaluation_run_id are filled in later by update_result()
        once the new evaluation run completes."""
        run = ExperimentRun(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            parent_evaluation_run_id=parent_evaluation_run_id,
            variant_config=variant_config,
            status=status,
            result_pipeline_version_id=result_pipeline_version_id,
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def update_result(
        self,
        *,
        experiment_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str,
        unified_score: float | None = None,
        score_delta: float | None = None,
        result_pipeline_version_id: uuid.UUID | None = None,
        result_evaluation_run_id: uuid.UUID | None = None,
    ) -> None:
        """Persist the outcome of a re-evaluation. unified_score/score_delta may
        legitimately be a REGRESSION (worse than the parent run) -- never clamped
        or overwritten with a better-looking fabricated value."""
        values: dict[str, object] = {
            "status": status,
            "updated_at": datetime.now(UTC),
        }
        if unified_score is not None:
            values["unified_score"] = unified_score
        if score_delta is not None:
            values["score_delta"] = score_delta
        if result_pipeline_version_id is not None:
            values["result_pipeline_version_id"] = result_pipeline_version_id
        if result_evaluation_run_id is not None:
            values["result_evaluation_run_id"] = result_evaluation_run_id

        stmt = (
            update(ExperimentRun)
            .where(
                ExperimentRun.id == experiment_run_id,
                ExperimentRun.organization_id == organization_id,
            )
            .values(**values)
        )
        await self._session.execute(stmt)

    async def get_by_id(
        self,
        *,
        experiment_run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ExperimentRun | None:
        stmt = select(ExperimentRun).where(
            ExperimentRun.id == experiment_run_id,
            ExperimentRun.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Sequence[ExperimentRun]:
        """Newest-first -- feeds the optimization timeline / iteration history."""
        stmt = (
            select(ExperimentRun)
            .where(
                ExperimentRun.pipeline_id == pipeline_id,
                ExperimentRun.organization_id == organization_id,
            )
            .order_by(ExperimentRun.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
