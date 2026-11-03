"""Repository -- deployments table.

All DB access for the deployments table.
No business logic -- pure persistence operations only.

Critical rules:
  - task_arn MUST be an immutable SHA tag (validated by DeploymentService).
  - All queries MUST include organization_id scoping (multi-tenancy -- Rule 30).
  - unified_score_at_deploy is written once at creation and never mutated.

Team 5 / Team 10 own this file.
Spec: .claude/specs/database.md section: deployments table
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment


class DeploymentRepository:
    """Data-access layer for deployments table.

    Constructor injection: pass an AsyncSession from get_db() FastAPI dependency.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Write operations ------------------------------------------------------

    async def create(
        self,
        *,
        pipeline_id: uuid.UUID,
        evaluation_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        task_arn: str,
        rollback_task_arn: str | None = None,
        unified_score_at_deploy: float | None = None,
    ) -> Deployment:
        """Insert a new deployment row and return the ORM instance.

        Args:
            pipeline_id: The pipeline being deployed.
            evaluation_run_id: The evaluation run that authorised this deployment.
            organization_id: Tenant scoping -- mandatory.
            task_arn: Immutable ECS task ARN (e.g. sha256:abc123). MUST NOT be 'latest'.
            rollback_task_arn: Previous Blue task ARN for instant revert.
            unified_score_at_deploy: Score snapshot at creation time (non-mutable).

        Returns:
            Persisted Deployment ORM instance with server-generated id.
        """
        deployment = Deployment(
            pipeline_id=pipeline_id,
            evaluation_run_id=evaluation_run_id,
            organization_id=organization_id,
            task_arn=task_arn,
            rollback_task_arn=rollback_task_arn,
            unified_score_at_deploy=unified_score_at_deploy,
        )
        self._session.add(deployment)
        await self._session.flush()
        await self._session.refresh(deployment)
        return deployment

    async def update_status(
        self,
        *,
        deployment_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str,
    ) -> None:
        """Transition deployment status (pending -> blue_green -> promoted | rolled_back | failed).

        Args:
            deployment_id: Target deployment PK.
            organization_id: Access control -- prevents cross-tenant writes.
            status: One of pending | blue_green | promoted | rolled_back | failed.

        Raises:
            ValueError: If deployment not found or org mismatch.
        """
        stmt = (
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.organization_id == organization_id,
            )
            .values(status=status)
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        if result.rowcount == 0:
            raise ValueError(
                f"Deployment {deployment_id} not found in org {organization_id}."
            )

    async def mark_deployed(
        self,
        *,
        deployment_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        """Record deployed_at timestamp when Blue/Green canary window opens."""
        stmt = (
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.organization_id == organization_id,
            )
            .values(status="blue_green", deployed_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def mark_promoted(
        self,
        *,
        deployment_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        """Record promoted_at when canary window passes and Green becomes production."""
        stmt = (
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.organization_id == organization_id,
            )
            .values(status="promoted", promoted_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def mark_rolled_back(
        self,
        *,
        deployment_id: uuid.UUID,
        organization_id: uuid.UUID,
        rollback_reason: str,
    ) -> None:
        """Record rolled_back_at and persist rollback_reason in a future JSONB column.

        For now reason is logged via audit_log; this method just timestamps the row.
        """
        stmt = (
            update(Deployment)
            .where(
                Deployment.id == deployment_id,
                Deployment.organization_id == organization_id,
            )
            .values(status="rolled_back", rolled_back_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    # -- Read operations -------------------------------------------------------

    async def get_by_id(
        self,
        *,
        deployment_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Deployment | None:
        """Fetch a single deployment by PK, org-scoped.

        Returns:
            Deployment ORM instance or None if not found.
        """
        stmt = select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Deployment | None:
        """Return the most recent deployment for a pipeline (for rollback retrieval).

        The rollback_task_arn on this row is the Blue task ARN to revert to.
        """
        stmt = (
            select(Deployment)
            .where(
                Deployment.pipeline_id == pipeline_id,
                Deployment.organization_id == organization_id,
                Deployment.status == "promoted",
            )
            .order_by(Deployment.promoted_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_blue_green_for_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Deployment | None:
        """Return the active canary deployment for a pipeline (for promote lookup).

        Used by DeploymentService.promote() to find the in-flight 'blue_green'
        row to transition to 'promoted'.
        """
        stmt = (
            select(Deployment)
            .where(
                Deployment.pipeline_id == pipeline_id,
                Deployment.organization_id == organization_id,
                Deployment.status == "blue_green",
            )
            .order_by(Deployment.deployed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_any_status_for_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Deployment | None:
        """Return the most recent deployment for a pipeline regardless of status.

        Used for the Deployment Center's live status/BlueGreenBar polling --
        unlike get_latest_for_pipeline (promoted-only) this surfaces
        pending/blue_green/failed rows too.
        """
        stmt = (
            select(Deployment)
            .where(
                Deployment.pipeline_id == pipeline_id,
                Deployment.organization_id == organization_id,
            )
            .order_by(Deployment.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[Deployment]:
        """List deployment history for a pipeline, newest first.

        Args:
            pipeline_id: Filter to this pipeline's deployments.
            organization_id: Tenant filter -- mandatory.
            limit: Page size (max 100 enforced at service layer).
            offset: Pagination offset.
        """
        stmt = (
            select(Deployment)
            .where(
                Deployment.pipeline_id == pipeline_id,
                Deployment.organization_id == organization_id,
            )
            .order_by(Deployment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
