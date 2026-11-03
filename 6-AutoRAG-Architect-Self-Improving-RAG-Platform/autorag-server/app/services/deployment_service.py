"""Business logic for Blue/Green ECS Fargate deployment and rollback.

Deploy Eligibility Gate (D-18 -- CLAUDE.md section 9):
  Score = 0.25*Recall + 0.35*Quality + 0.25*Faithfulness - 0.10*Latency - 0.05*Cost
  Gate thresholds:
    unified_score >= 0.85  -> autonomous deploy eligible
    0.70 <= score < 0.85   -> HITL required (approval_token mandatory)
    score < 0.70           -> hard block (Diagnoser + Improver loop triggered)
  Hard blockers (non-bypassable, override HITL):
    faithfulness < 0.5     -> ALWAYS blocked, regardless of total score or approval
    adversarial_passed == False -> ALWAYS blocked

Architecture: routes -> DeploymentService -> DeploymentRepository (Rule 10).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeploymentBlockedError, PipelineNotFoundError
from app.models.deployment import Deployment
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.deployment_repository import DeploymentRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.pipeline_repository import PipelineRepository
from app.services.base import BaseService

logger = structlog.get_logger(__name__)

# Gate thresholds -- sourced from CLAUDE.md section 9
_SCORE_DEPLOY_THRESHOLD = 0.85
_SCORE_HITL_THRESHOLD = 0.70
_FAITHFULNESS_HARD_BLOCK = 0.50


def _serialize_deployment(deployment: Deployment) -> dict:
    """Map a Deployment ORM row to the plain dict returned across the API boundary.

    Single serialization point (Rule 10) so /history and /status stay consistent
    with the Deployment shape frontend/types/index.ts expects.
    """
    return {
        "id": str(deployment.id),
        "pipeline_id": str(deployment.pipeline_id),
        "status": deployment.status,
        "task_arn": deployment.task_arn,
        "rollback_task_arn": deployment.rollback_task_arn,
        "unified_score_at_deploy": (
            float(deployment.unified_score_at_deploy)
            if deployment.unified_score_at_deploy is not None
            else None
        ),
        "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
        "promoted_at": deployment.promoted_at.isoformat() if deployment.promoted_at else None,
        "rolled_back_at": (
            deployment.rolled_back_at.isoformat() if deployment.rolled_back_at else None
        ),
        "created_at": deployment.created_at.isoformat(),
    }


class DeploymentService(BaseService):
    """Orchestrates deployments via Deployer Agent. Called by routes/deploy.py."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._deploy_repo = DeploymentRepository(db)
        self._eval_repo = EvaluationRepository(db)
        self._pipeline_repo = PipelineRepository(db)
        self._audit = AuditLogRepository(db)

    def verify_deployment_gates(
        self,
        *,
        unified_score: float,
        faithfulness: float,
        adversarial_passed: bool,
        approval_token: str | None = None,
    ) -> str:
        """Verify all three deployment eligibility gates.

        Faithfulness hard-block runs first because it overrides ALL other
        conditions including HITL approval -- this is non-bypassable per
        CLAUDE.md section 9 Forbidden Patterns #2.

        Args:
            unified_score: Weighted composite score (0.0 -- 1.0).
            faithfulness: Faithfulness component. < 0.5 = hard block.
            adversarial_passed: True only when all 10 adversarial Q&A pass.
            approval_token: Required when score is in HITL zone (0.70 -- 0.84).

        Returns:
            "autonomous" | "hitl_approved"

        Raises:
            DeploymentBlockedError: If any gate fails (non-bypassable).
        """
        # Hard block 1: faithfulness -- overrides HITL, overrides score
        if faithfulness < _FAITHFULNESS_HARD_BLOCK:
            raise DeploymentBlockedError(
                reason=(
                    f"Faithfulness {faithfulness:.3f} < {_FAITHFULNESS_HARD_BLOCK} "
                    "(hard block -- non-bypassable per CLAUDE.md section 9)"
                ),
                score=unified_score,
            )

        # Hard block 2: adversarial -- all 10 questions must pass
        if not adversarial_passed:
            raise DeploymentBlockedError(
                reason=(
                    "Adversarial Q&A suite failed (pass_rate < 1.0). "
                    "Fabricated answers detected -- deployment blocked."
                ),
                score=unified_score,
            )

        # Score gate: hard block below HITL threshold
        if unified_score < _SCORE_HITL_THRESHOLD:
            raise DeploymentBlockedError(
                reason=(
                    f"Unified Score {unified_score:.3f} < {_SCORE_HITL_THRESHOLD} "
                    "(hard block -- Diagnoser + Improver loop required)"
                ),
                score=unified_score,
            )

        # HITL zone: score is in [0.70, 0.85) -- requires signed approval token
        if unified_score < _SCORE_DEPLOY_THRESHOLD:
            if not approval_token:
                raise DeploymentBlockedError(
                    reason=(
                        f"Unified Score {unified_score:.3f} is in HITL zone "
                        f"[{_SCORE_HITL_THRESHOLD}, {_SCORE_DEPLOY_THRESHOLD}). "
                        "approval_token required from Mahesh Kumar via SendGrid + Twilio."
                    ),
                    score=unified_score,
                )
            return "hitl_approved"

        # All gates clear: autonomous deploy eligible
        return "autonomous"

    async def deploy(
        self,
        *,
        run_id: str,
        organization_id: str,
        task_arn: str,
        approval_token: str | None = None,
        x_trace_id: str,
    ) -> dict:
        """Trigger a Blue/Green ECS Fargate deployment for a completed eval run.

        Steps:
          1. Load the evaluation_run by run_id and org-scope.
          2. Verify all three deployment gates (raises DeploymentBlockedError on failure).
          3. Retrieve the latest promoted deployment for the pipeline (rollback ARN).
          4. Create a new deployment row (status=pending -> blue_green).
          5. Write deploy_started audit event.
          6. Return deployment metadata for the Deployer Agent to monitor.

        Args:
            run_id: The evaluation run UUID that authorised this deployment.
            organization_id: Tenant scoping.
            task_arn: Immutable ECS task ARN -- MUST NOT be 'latest'.
            approval_token: Required when score is in HITL zone (0.70 -- 0.84).
            x_trace_id: Request correlation ID (propagated from API header).

        Returns:
            Dict with deploy_status, deployment_id, pipeline_id, and score snapshot.

        Raises:
            DeploymentBlockedError: If any quality gate fails.
            PipelineNotFoundError: If the referenced pipeline does not exist.
            ValueError: If task_arn contains 'latest' tag (forbidden by Rule 90).
        """
        if "latest" in task_arn.lower():
            raise ValueError(
                "task_arn must use an immutable SHA tag -- 'latest' is forbidden (Rule 90)."
            )

        org_uuid = uuid.UUID(organization_id)
        run_uuid = uuid.UUID(run_id)

        eval_run = await self._eval_repo.get_by_run_id(
            run_id=run_uuid,
            organization_id=org_uuid,
        )
        if eval_run is None:
            raise ValueError(
                f"EvaluationRun run_id={run_id} not found in org {organization_id}."
            )

        pipeline = await self._pipeline_repo.get_by_id(
            pipeline_id=eval_run.pipeline_id,
            organization_id=org_uuid,
        )
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {eval_run.pipeline_id} not found in org {organization_id}."
            )

        # All gates -- raises DeploymentBlockedError on any failure
        gate_result = self.verify_deployment_gates(
            unified_score=float(eval_run.unified_score or 0.0),
            faithfulness=float(eval_run.faithfulness or 0.0),
            adversarial_passed=eval_run.adversarial_passed,
            approval_token=approval_token,
        )

        # Retrieve existing promoted deployment for rollback ARN
        latest = await self._deploy_repo.get_latest_for_pipeline(
            pipeline_id=eval_run.pipeline_id,
            organization_id=org_uuid,
        )
        rollback_task_arn = latest.task_arn if latest else None

        deployment = await self._deploy_repo.create(
            pipeline_id=eval_run.pipeline_id,
            evaluation_run_id=eval_run.id,
            organization_id=org_uuid,
            task_arn=task_arn,
            rollback_task_arn=rollback_task_arn,
            unified_score_at_deploy=float(eval_run.unified_score or 0.0),
        )

        await self._audit.insert(
            event_type="deploy_started",
            organization_id=org_uuid,
            run_id=run_uuid,
            payload={
                "deployment_id": str(deployment.id),
                "pipeline_id": str(eval_run.pipeline_id),
                "task_arn": task_arn,
                "gate_result": gate_result,
                "unified_score": float(eval_run.unified_score or 0.0),
                "faithfulness": float(eval_run.faithfulness or 0.0),
                "adversarial_passed": eval_run.adversarial_passed,
            },
            trace_id=x_trace_id,
        )

        # Open the Blue/Green canary window
        await self._deploy_repo.mark_deployed(
            deployment_id=deployment.id,
            organization_id=org_uuid,
        )

        await self.db.commit()

        logger.bind(
            deployment_id=str(deployment.id),
            pipeline_id=str(eval_run.pipeline_id),
            gate_result=gate_result,
            unified_score=float(eval_run.unified_score or 0.0),
            x_trace_id=x_trace_id,
        ).info("deployment.started")

        return {
            "deploy_status": "blue_green",
            "gate_result": gate_result,
            "deployment_id": str(deployment.id),
            "pipeline_id": str(eval_run.pipeline_id),
            "task_arn": task_arn,
            "unified_score_at_deploy": float(eval_run.unified_score or 0.0),
            "rollback_task_arn": rollback_task_arn,
        }

    async def rollback(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        rollback_reason: str,
        x_trace_id: str,
    ) -> dict:
        """Revert to the previous Blue task ARN.

        Steps:
          1. Fetch the latest promoted deployment for the pipeline.
          2. Validate that a rollback_task_arn exists (previous Blue ARN).
          3. Mark the deployment as rolled_back.
          4. Write rollback_triggered audit event.
          5. Return rollback_task_arn for the Deployer Agent to swap ALB weights.

        Args:
            pipeline_id: The pipeline to roll back.
            organization_id: Tenant scoping.
            rollback_reason: Human-readable reason (logged to audit_log).
            x_trace_id: Request correlation ID.

        Returns:
            Dict with rollback_task_arn and deployment_id for the Deployer Agent.

        Raises:
            ValueError: If no promoted deployment exists or rollback_task_arn absent.
            PipelineNotFoundError: If pipeline does not exist.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        pipeline = await self._pipeline_repo.get_by_id(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
        )
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )

        latest = await self._deploy_repo.get_latest_for_pipeline(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
        )
        if latest is None:
            raise ValueError(
                f"No promoted deployment found for pipeline {pipeline_id}. Nothing to roll back."
            )
        if not latest.rollback_task_arn:
            raise ValueError(
                f"Deployment {latest.id} has no rollback_task_arn. "
                "Cannot roll back to a prior Blue task."
            )

        await self._deploy_repo.mark_rolled_back(
            deployment_id=latest.id,
            organization_id=org_uuid,
            rollback_reason=rollback_reason,
        )

        await self._audit.insert(
            event_type="rollback_triggered",
            organization_id=org_uuid,
            run_id=None,
            payload={
                "deployment_id": str(latest.id),
                "pipeline_id": pipeline_id,
                "rollback_task_arn": latest.rollback_task_arn,
                "reason": rollback_reason,
            },
            trace_id=x_trace_id,
        )

        await self.db.commit()

        logger.bind(
            deployment_id=str(latest.id),
            pipeline_id=pipeline_id,
            rollback_task_arn=latest.rollback_task_arn,
            x_trace_id=x_trace_id,
        ).info("deployment.rolled_back")

        return {
            "rollback_status": "triggered",
            "deployment_id": str(latest.id),
            "pipeline_id": pipeline_id,
            "rollback_task_arn": latest.rollback_task_arn,
            "reason": rollback_reason,
        }

    async def promote(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        x_trace_id: str,
    ) -> dict:
        """Promote the active Blue/Green canary to 100% Green (production).

        Steps:
          1. Fetch the pipeline's latest 'blue_green' deployment (the open canary).
          2. Mark it 'promoted' (records promoted_at).
          3. Write deploy_completed audit event (the 14 approved audit_log event
             types -- models/audit_log.py -- have no dedicated 'promoted' type;
             reusing deploy_completed avoids a schema migration).

        Args:
            pipeline_id: The pipeline whose canary should be promoted.
            organization_id: Tenant scoping.
            x_trace_id: Request correlation ID.

        Returns:
            Dict with promote_status and deployment_id.

        Raises:
            ValueError: If no active 'blue_green' deployment exists to promote.
            PipelineNotFoundError: If pipeline does not exist.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        pipeline = await self._pipeline_repo.get_by_id(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
        )
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )

        active = await self._deploy_repo.get_latest_blue_green_for_pipeline(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
        )
        if active is None:
            raise ValueError(
                f"No active Blue/Green canary found for pipeline {pipeline_id}. "
                "Nothing to promote."
            )

        await self._deploy_repo.mark_promoted(
            deployment_id=active.id,
            organization_id=org_uuid,
        )

        await self._audit.insert(
            event_type="deploy_completed",
            organization_id=org_uuid,
            run_id=active.evaluation_run_id,
            payload={
                "deployment_id": str(active.id),
                "pipeline_id": pipeline_id,
                "task_arn": active.task_arn,
            },
            trace_id=x_trace_id,
        )

        await self.db.commit()

        logger.bind(
            deployment_id=str(active.id),
            pipeline_id=pipeline_id,
            x_trace_id=x_trace_id,
        ).info("deployment.promoted")

        return {
            "promote_status": "promoted",
            "deployment_id": str(active.id),
            "pipeline_id": pipeline_id,
            "task_arn": active.task_arn,
        }

    async def get_history(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """List deployment history for a pipeline, newest first (Chapter 24 — DeploymentHistory)."""
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        rows = await self._deploy_repo.list_by_pipeline(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            limit=limit,
            offset=offset,
        )

        return {
            "pipeline_id": pipeline_id,
            "deployments": [_serialize_deployment(row) for row in rows],
        }

    async def get_current_status(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
    ) -> dict:
        """Return the most recent deployment (any status) for live BlueGreenBar polling."""
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        latest = await self._deploy_repo.get_latest_any_status_for_pipeline(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
        )

        return {
            "pipeline_id": pipeline_id,
            "deployment": _serialize_deployment(latest) if latest else None,
        }
