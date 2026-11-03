"""Agent 9 -- Deployer node: Blue/Green ECS Fargate deploy + auto-rollback.

Spec: .claude/specs/agents/09-deployer.md
Rules: 60-agents.md, 90-devops-deployment.md, deployment-policies.md

Deployment pipeline:
  1. Verify all deployment gates (DeploymentService) -- non-bypassable
  2. Reject "latest" image tags -- immutable SHA required (Rule 90)
  3. Register new ECS task definition revision with new ECR image URI
  4. Update ECS service to use new task definition
  5. Shift ALB listener: Blue 90% -> Green 10% (canary start)
  6. Monitor canary window (canary_window_minutes from settings):
       - Auto-rollback if error_rate > 1% | p95 > 3000ms | score drop > 0.10
  7. On success: shift ALB to Green 100%; deregister Blue from listener
  8. On failure: restore Blue 100%; deregister Green; write rollback_reason
  9. Write audit_log entry; update execution_trace

Retry policy: all retries are explicit graph edges (graph-state-governance Rule 4).
Never use inline retry loops.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.state import GraphState
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.deployment_service import DeploymentBlockedError, DeploymentService

logger = logging.getLogger(__name__)

# Canary poll cadence -- every 30 seconds; stays well within the 10-minute window
_CANARY_POLL_INTERVAL_S = 30


async def deployer_node(state: GraphState) -> GraphState:
    """Execute Blue/Green ECS Fargate deploy with canary monitoring and auto-rollback."""
    if state.get("guardrail_blocked"):
        logger.warning(
            "deployer_skipped_guardrail_blocked",
            extra={"x_trace_id": state.get("x_trace_id", "")},
        )
        return state

    node_start = time.monotonic()
    x_trace_id: str = state.get("x_trace_id") or ""
    pipeline_id: str = state.get("pipeline_id") or ""
    organization_id: str = state.get("organization_id") or ""
    existing_trace: list[dict[str, Any]] = list(state.get("execution_trace") or [])

    ecr_image_uri: str = state.get("ecr_image_uri") or ""
    approval_token: str | None = state.get("approval_token")
    baseline_score: float = float(state.get("unified_score") or 0.0)
    faithfulness: float = float(state.get("faithfulness") or 0.0)
    adversarial_passed: bool = bool(state.get("adversarial_pass_rate") == 1.0)

    logger.info(
        "deployer_node_started",
        extra={
            "x_trace_id": x_trace_id,
            "pipeline_id": pipeline_id,
            "ecr_image_tag_present": bool(ecr_image_uri),
        },
    )

    # ── Gate 0: Reject mutable image tags (Rule 90) ───────────────────────────
    if not ecr_image_uri:
        return await _fail(
            state, x_trace_id, existing_trace, node_start,
            reason="ecr_image_uri_missing",
        )
    if ecr_image_uri.endswith(":latest"):
        return await _fail(
            state, x_trace_id, existing_trace, node_start,
            reason="ecr_image_uri_uses_latest_tag_forbidden",
        )

    # ── Gate 1: Deployment quality + safety gates (DeploymentService) ─────────
    async with AsyncSessionLocal() as db:
        deploy_svc = DeploymentService(db=db)
        try:
            deploy_mode = deploy_svc.verify_deployment_gates(
                unified_score=baseline_score,
                faithfulness=faithfulness,
                adversarial_passed=adversarial_passed,
                approval_token=approval_token,
            )
        except DeploymentBlockedError as exc:
            logger.warning(
                "deployer_gate_blocked",
                extra={"x_trace_id": x_trace_id, "reason": str(exc)},
            )
            return await _fail(
                state, x_trace_id, existing_trace, node_start,
                reason=f"gate_blocked:{exc}",
            )

    logger.info(
        "deployer_gates_passed",
        extra={"x_trace_id": x_trace_id, "deploy_mode": deploy_mode},
    )

    # ── Step 2: Register new ECS task definition ───────────────────────────────
    import boto3  # imported here so app starts without AWS creds in local/dev

    ecs = boto3.client("ecs", region_name=settings.aws_region)
    elbv2 = boto3.client("elbv2", region_name=settings.aws_region)
    cloudwatch = boto3.client("cloudwatch", region_name=settings.aws_region)

    current_td_arn = await _get_current_task_def_arn(ecs)
    new_td_arn = await _register_task_definition(ecs, current_td_arn, ecr_image_uri)
    ecs_task_arn = new_td_arn

    logger.info(
        "deployer_task_def_registered",
        extra={"x_trace_id": x_trace_id, "new_task_def": new_td_arn},
    )

    # ── Step 3: Update ECS service to use new task definition ─────────────────
    await _update_ecs_service(ecs, new_td_arn)

    # ── Step 4: Canary start -- ALB listener Blue 90% / Green 10% ─────────────
    await _set_alb_weights(elbv2, blue_weight=90, green_weight=10)

    logger.info(
        "deployer_canary_started",
        extra={
            "x_trace_id": x_trace_id,
            "canary_window_minutes": settings.canary_window_minutes,
        },
    )

    # ── Step 5: Monitor canary window ─────────────────────────────────────────
    canary_ok, rollback_reason = await _monitor_canary(
        cloudwatch=cloudwatch,
        x_trace_id=x_trace_id,
        baseline_score=baseline_score,
        canary_window_minutes=settings.canary_window_minutes,
        poll_interval_s=_CANARY_POLL_INTERVAL_S,
    )

    active_task_arn: str
    deploy_status: Literal["success", "rolled_back", "failed"]
    rollback_reason_out: str | None = None

    if canary_ok:
        # ── Success: promote Green to 100% ─────────────────────────────────
        await _set_alb_weights(elbv2, blue_weight=0, green_weight=100)
        active_task_arn = new_td_arn
        deploy_status = "success"
        logger.info(
            "deployer_promotion_complete",
            extra={"x_trace_id": x_trace_id, "active_task_arn": active_task_arn},
        )
    else:
        # ── Rollback: restore Blue 100% ───────────────────────────────────
        await _set_alb_weights(elbv2, blue_weight=100, green_weight=0)
        await _update_ecs_service(ecs, current_td_arn)
        active_task_arn = current_td_arn
        deploy_status = "rolled_back"
        rollback_reason_out = rollback_reason
        logger.warning(
            "deployer_rollback_complete",
            extra={
                "x_trace_id": x_trace_id,
                "rollback_reason": rollback_reason,
                "restored_task_def": current_td_arn,
            },
        )

    # ── Step 6: Write audit_log (INSERT-only, 14 approved event types) ────────
    # "deploy_rolled_back" is NOT an approved event_type (APPROVED_EVENT_TYPES
    # only has "rollback_triggered") -- using it here would raise ValueError
    # inside AuditLogRepository.insert() on every canary rollback.
    audit_event_type = "deploy_completed" if canary_ok else "rollback_triggered"
    async with AsyncSessionLocal() as db:
        audit_repo = AuditLogRepository(db)
        run_id_raw = state.get("run_id")
        await audit_repo.insert(
            event_type=audit_event_type,
            run_id=uuid.UUID(run_id_raw) if run_id_raw else None,
            organization_id=uuid.UUID(organization_id) if organization_id else None,
            trace_id=x_trace_id,
            payload={
                "pipeline_id": pipeline_id,
                "ecr_image_uri": ecr_image_uri,
                "deploy_mode": deploy_mode,
                "task_def_arn": ecs_task_arn,
                "active_task_arn": active_task_arn,
                "deploy_status": deploy_status,
                "rollback_reason": rollback_reason_out,
                "baseline_unified_score": baseline_score,
            },
        )

    latency_ms = int((time.monotonic() - node_start) * 1000)

    return {
        **state,
        "deploy_status": deploy_status,
        "ecs_task_arn": ecs_task_arn,
        "active_task_arn": active_task_arn,
        "rollback_reason": rollback_reason_out,
        "execution_trace": existing_trace + [_trace_entry(
            x_trace_id=x_trace_id,
            graph_state_version=state.get("graph_state_version", "v1.0"),
            latency_ms=latency_ms,
            status="success" if canary_ok else "rolled_back",
            retry_count=state.get("retry_count") or 0,
            deploy_status=deploy_status,
            deploy_mode=deploy_mode,
        )],
    }


# ── AWS helpers (all wrapped in asyncio.to_thread -- boto3 is synchronous) ─────


async def _get_current_task_def_arn(ecs: Any) -> str:
    """Return the active task definition ARN from the ECS service."""
    resp = await asyncio.to_thread(
        ecs.describe_services,
        cluster=settings.ecs_cluster_name,
        services=[settings.ecs_service_name],
    )
    service = resp["services"][0]
    return str(service["taskDefinition"])


async def _register_task_definition(ecs: Any, current_td_arn: str, new_image_uri: str) -> str:
    """Clone the current task definition with the new ECR image URI."""
    # Describe the current to clone all settings
    current = await asyncio.to_thread(
        ecs.describe_task_definition,
        taskDefinition=current_td_arn,
    )
    td = current["taskDefinition"]

    # Replace image in the first container definition
    container_defs = td.get("containerDefinitions", [])
    if container_defs:
        container_defs[0]["image"] = new_image_uri

    resp = await asyncio.to_thread(
        ecs.register_task_definition,
        family=td["family"],
        networkMode=td.get("networkMode", "awsvpc"),
        requiresCompatibilities=td.get("requiresCompatibilities", ["FARGATE"]),
        cpu=td.get("cpu", "512"),
        memory=td.get("memory", "1024"),
        executionRoleArn=td.get("executionRoleArn", ""),
        taskRoleArn=td.get("taskRoleArn", ""),
        containerDefinitions=container_defs,
    )
    return str(resp["taskDefinition"]["taskDefinitionArn"])


async def _update_ecs_service(ecs: Any, task_def_arn: str) -> None:
    """Update the ECS service to use the specified task definition."""
    await asyncio.to_thread(
        ecs.update_service,
        cluster=settings.ecs_cluster_name,
        service=settings.ecs_service_name,
        taskDefinition=task_def_arn,
        forceNewDeployment=True,
    )


async def _set_alb_weights(elbv2: Any, *, blue_weight: int, green_weight: int) -> None:
    """Modify the ALB listener rule to split traffic between Blue and Green target groups."""
    if not settings.alb_listener_arn:
        return  # Skip in local/dev where ALB is not configured

    # Fetch existing listener rules to find the one routing to our target groups
    rules_resp = await asyncio.to_thread(
        elbv2.describe_rules,
        ListenerArn=settings.alb_listener_arn,
    )
    rules: list[dict[str, Any]] = rules_resp.get("Rules", [])

    target_rule_arn: str | None = None
    for rule in rules:
        for action in rule.get("Actions", []):
            if action.get("Type") == "forward":
                tg_config = action.get("ForwardConfig", {})
                tg_arns = [
                    tg["TargetGroupArn"]
                    for tg in tg_config.get("TargetGroups", [])
                ]
                if (
                    settings.alb_blue_target_group_arn in tg_arns
                    or settings.alb_green_target_group_arn in tg_arns
                ):
                    target_rule_arn = rule["RuleArn"]
                    break
        if target_rule_arn:
            break

    if not target_rule_arn:
        return  # No matching rule found -- skip (dev/local)

    new_actions = [
        {
            "Type": "forward",
            "ForwardConfig": {
                "TargetGroups": [
                    {
                        "TargetGroupArn": settings.alb_blue_target_group_arn,
                        "Weight": blue_weight,
                    },
                    {
                        "TargetGroupArn": settings.alb_green_target_group_arn,
                        "Weight": green_weight,
                    },
                ]
            },
        }
    ]
    await asyncio.to_thread(
        elbv2.modify_rule,
        RuleArn=target_rule_arn,
        Actions=new_actions,
    )


async def _monitor_canary(
    *,
    cloudwatch: Any,
    x_trace_id: str,
    baseline_score: float,
    canary_window_minutes: int,
    poll_interval_s: int,
) -> tuple[bool, str | None]:
    """Poll CloudWatch metrics during the canary window. Return (ok, rollback_reason)."""
    deadline = time.monotonic() + canary_window_minutes * 60

    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval_s)

        try:
            error_rate = await _get_cloudwatch_metric(
                cloudwatch,
                metric_name="ErrorRate",
                namespace="AutoRAG",
                stat="Average",
                period_seconds=60,
            )
            p95_latency_ms = await _get_cloudwatch_metric(
                cloudwatch,
                metric_name="P95LatencyMs",
                namespace="AutoRAG",
                stat="p95",
                period_seconds=60,
            )
        except Exception as exc:  # noqa: BLE001 -- CloudWatch access may not be available in dev
            logger.warning(
                "deployer_canary_metrics_unavailable",
                extra={"x_trace_id": x_trace_id, "error": str(exc)},
            )
            continue

        if error_rate is not None and error_rate > settings.canary_error_rate_threshold:
            return False, f"error_rate={error_rate:.4f}_exceeds_{settings.canary_error_rate_threshold}"

        if p95_latency_ms is not None and p95_latency_ms > settings.canary_latency_p95_ms_threshold:
            return False, f"p95_latency_ms={p95_latency_ms:.0f}_exceeds_{settings.canary_latency_p95_ms_threshold}"

        logger.info(
            "deployer_canary_poll_ok",
            extra={
                "x_trace_id": x_trace_id,
                "error_rate": error_rate,
                "p95_latency_ms": p95_latency_ms,
                "remaining_s": int(deadline - time.monotonic()),
            },
        )

    return True, None


async def _get_cloudwatch_metric(
    cloudwatch: Any,
    *,
    metric_name: str,
    namespace: str,
    stat: str,
    period_seconds: int,
) -> float | None:
    """Fetch the most recent datapoint for a CloudWatch metric. Returns None if no data."""
    now = datetime.now(UTC)
    start = now.replace(second=0, microsecond=0)
    import datetime as dt  # stdlib datetime needed for timedelta

    resp = await asyncio.to_thread(
        cloudwatch.get_metric_statistics,
        Namespace=namespace,
        MetricName=metric_name,
        StartTime=(start - dt.timedelta(seconds=period_seconds * 3)).isoformat(),
        EndTime=start.isoformat(),
        Period=period_seconds,
        Statistics=[stat] if stat in ("Average", "Sum", "SampleCount") else [],
        ExtendedStatistics=[stat] if stat not in ("Average", "Sum", "SampleCount") else [],
    )
    datapoints = resp.get("Datapoints", [])
    if not datapoints:
        return None
    latest = sorted(datapoints, key=lambda d: d["Timestamp"])[-1]
    return float(latest.get(stat, latest.get("Average", 0.0)))


async def _fail(
    state: GraphState,
    x_trace_id: str,
    existing_trace: list[dict[str, Any]],
    node_start: float,
    reason: str,
) -> GraphState:
    latency_ms = int((time.monotonic() - node_start) * 1000)
    return {
        **state,
        "deploy_status": "failed",
        "rollback_reason": reason,
        "execution_trace": existing_trace + [_trace_entry(
            x_trace_id=x_trace_id,
            graph_state_version=state.get("graph_state_version", "v1.0"),
            latency_ms=latency_ms,
            status="blocked",
            retry_count=state.get("retry_count") or 0,
            rollback_reason=reason,
        )],
    }


def _trace_entry(
    *,
    x_trace_id: str,
    graph_state_version: str,
    latency_ms: int,
    status: str,
    retry_count: int,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "node": "deployer",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "x_trace_id": x_trace_id,
        "graph_state_version": graph_state_version,
        "latency_ms": latency_ms,
        "status": status,
        "retry_count": retry_count,
        **extra,
    }
