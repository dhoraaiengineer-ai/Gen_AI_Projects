"""Repository — evaluation_runs table.

All DB access for the evaluation_runs table.
No business logic — pure persistence operations only.

Critical rules:
  - faithfulness < 0.5 is a hard block — enforced in is_deploy_eligible property
    on the ORM model; the repository just stores and retrieves the value.
  - All queries MUST include organization_id scoping (multi-tenancy — Rule 30).
  - run_id is the correlation ID shared with LangGraph — always UNIQUE.

Team 5 owns this file.
Spec: .claude/specs/database.md § evaluation_runs table
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.evaluation_run import EvaluationRun


class EvaluationRepository:
    """Data-access layer for evaluation_runs table.

    Constructor injection: pass an AsyncSession from get_db() FastAPI dependency.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write operations ──────────────────────────────────────────────────────

    async def create(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
        run_id: uuid.UUID,
        dataset_version: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> EvaluationRun:
        """Insert a new evaluation_run row and return the ORM instance.

        Args:
            pipeline_id: The pipeline being evaluated.
            organization_id: Tenant scoping — mandatory.
            run_id: Correlation ID from LangGraph — must be unique.
            dataset_version: Eval dataset version string (e.g. "v1.2.0").
            **kwargs: Optional column overrides.

        Returns:
            Persisted EvaluationRun ORM instance with server-generated id.
        """
        run = EvaluationRun(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            run_id=run_id,
            dataset_version=dataset_version,
            **kwargs,
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def update_score(
        self,
        *,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        unified_score: float | None,
        recall: float | None = None,
        quality: float | None = None,
        faithfulness: float | None = None,
        latency_p95_ms: int | None = None,
        cost_usd: float | None = None,
        ragas_metrics: dict | None = None,
        failure_taxonomy: dict | None = None,
        adversarial_passed: bool | None = None,
        status: str | None = None,
        agent_execution_metadata: dict | None = None,
    ) -> None:
        """Update score components on an evaluation_run.

        Called by the Evaluator agent after the 3-layer evaluation completes.
        The repository does NOT enforce the faithfulness gate — the service
        layer checks is_deploy_eligible on the ORM model before proceeding.

        Args:
            run_id: Correlation ID (UNIQUE on evaluation_runs table).
            organization_id: Access control — prevents cross-tenant writes.
            unified_score: Weighted composite score.
            faithfulness: If < 0.5 → is_deploy_eligible returns False (hard block).
        """
        values: dict = {
            "updated_at": datetime.now(UTC),
        }
        if unified_score is not None:
            values["unified_score"] = unified_score
        if recall is not None:
            values["recall"] = recall
        if quality is not None:
            values["quality"] = quality
        if faithfulness is not None:
            values["faithfulness"] = faithfulness
        if latency_p95_ms is not None:
            values["latency_p95_ms"] = latency_p95_ms
        if cost_usd is not None:
            values["cost_usd"] = cost_usd
        if ragas_metrics is not None:
            values["ragas_metrics"] = ragas_metrics
        if failure_taxonomy is not None:
            values["failure_taxonomy"] = failure_taxonomy
        if adversarial_passed is not None:
            values["adversarial_passed"] = adversarial_passed
        if status is not None:
            values["status"] = status
        if agent_execution_metadata is not None:
            values["agent_execution_metadata"] = agent_execution_metadata

        stmt = (
            update(EvaluationRun)
            .where(
                EvaluationRun.run_id == run_id,
                EvaluationRun.organization_id == organization_id,
            )
            .values(**values)
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        if result.rowcount == 0:
            raise ValueError(
                f"EvaluationRun run_id={run_id} not found in org {organization_id}."
            )

    async def update_status(
        self,
        *,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str,
    ) -> None:
        """Fast-path status update (pending → running → completed/blocked)."""
        stmt = (
            update(EvaluationRun)
            .where(
                EvaluationRun.run_id == run_id,
                EvaluationRun.organization_id == organization_id,
            )
            .values(status=status, updated_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    # ── Read operations ───────────────────────────────────────────────────────

    async def get_by_run_id(
        self,
        *,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> EvaluationRun | None:
        """Fetch a single evaluation_run by its LangGraph correlation run_id.

        Returns:
            EvaluationRun ORM instance or None if not found.
        """
        stmt = select(EvaluationRun).where(
            EvaluationRun.run_id == run_id,
            EvaluationRun.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        *,
        evaluation_run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> EvaluationRun | None:
        """Fetch a single evaluation_run by primary key, org-scoped."""
        stmt = select(EvaluationRun).where(
            EvaluationRun.id == evaluation_run_id,
            EvaluationRun.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationRun]:
        """List evaluation_runs for a pipeline, newest first.

        Args:
            pipeline_id: Filter to runs for this specific pipeline.
            organization_id: Tenant filter — mandatory.
            status: Optional status filter.
            limit: Page size.
            offset: Pagination offset.
        """
        stmt = (
            select(EvaluationRun)
            .where(
                EvaluationRun.pipeline_id == pipeline_id,
                EvaluationRun.organization_id == organization_id,
            )
            .order_by(EvaluationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(EvaluationRun.status == status)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_latest_by_pipeline_ids(
        self,
        *,
        pipeline_ids: Sequence[uuid.UUID],
        organization_id: uuid.UUID,
    ) -> dict[uuid.UUID, EvaluationRun]:
        """Fetch each pipeline's single most-recent evaluation_run in ONE query.

        26-Jul-2026 fix (P0 UAT finding): PipelineService.list_by_org() previously
        had no way to attach latest_run to the list response, forcing the frontend
        (hooks/use-pipelines.ts) into an N+1 fan-out -- one GET /pipelines/{id}
        request per pipeline, fired concurrently via Promise.all. Confirmed via
        live testing that at ~20 pipelines this burst (21 simultaneous requests
        from a single page load) was large enough to intermittently overwhelm the
        local backend regardless of frontend dev/production build -- a genuine
        request-volume defect, not a dev-server artifact. This method lets the
        list endpoint return latest_run inline, eliminating the fan-out entirely.

        Uses a ROW_NUMBER() window function partitioned by pipeline_id so this
        stays a single query regardless of how many evaluation runs each
        pipeline has accumulated.

        Returns:
            Dict mapping pipeline_id -> its latest EvaluationRun. Pipelines with
            no runs yet are simply absent from the dict (caller treats that as
            latest_run=None, same as the existing single-pipeline GET route).
        """
        if not pipeline_ids:
            return {}

        row_number = (
            func.row_number()
            .over(
                partition_by=EvaluationRun.pipeline_id,
                order_by=EvaluationRun.created_at.desc(),
            )
            .label("rn")
        )
        subq = (
            select(EvaluationRun, row_number)
            .where(
                EvaluationRun.pipeline_id.in_(pipeline_ids),
                EvaluationRun.organization_id == organization_id,
            )
            .subquery()
        )
        latest_run_alias = aliased(EvaluationRun, subq)
        stmt = select(latest_run_alias).where(subq.c.rn == 1)
        result = await self._session.execute(stmt)
        runs = result.scalars().all()
        return {run.pipeline_id: run for run in runs}

    async def list_by_org(
        self,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationRun]:
        """List all evaluation_runs for an org across all pipelines, newest first."""
        stmt = (
            select(EvaluationRun)
            .where(EvaluationRun.organization_id == organization_id)
            .order_by(EvaluationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
