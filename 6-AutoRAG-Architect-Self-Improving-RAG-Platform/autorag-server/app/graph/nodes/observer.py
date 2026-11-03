"""Agent 6 — Observer node: watch production latency, cost, quality."""
# Pushes metrics to Prometheus; triggers diagnosis if thresholds breached

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.state import GraphState
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.evaluation_repository import EvaluationRepository

logger = logging.getLogger(__name__)


async def observer_node(state: GraphState) -> GraphState:
    """Collect run metrics and push to Prometheus; set observation_flags."""
    node_start = time.monotonic()

    x_trace_id: str = state.get("x_trace_id") or ""
    run_id: str = state.get("run_id") or ""
    pipeline_id: str = state.get("pipeline_id") or ""
    organization_id: str = state.get("organization_id") or ""
    provider: str = state.get("llm_provider_used") or "gemini-flash-3.5"
    existing_trace: list[dict[str, Any]] = list(state.get("execution_trace") or [])

    logger.info(
        "Observer node started",
        extra={
            "x_trace_id": x_trace_id,
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "organization_id": organization_id,
        },
    )

    # 1. Record p95 latency, error_rate, unified_score from state
    unified_score = state.get("unified_score") or 0.0
    latency_p95_ms = state.get("latency_p95_ms") or 0
    cost_per_query_usd = state.get("cost_per_query_usd") or 0.0

    # 2. Increment retry_count as defined by the state contract
    retry_count = (state.get("retry_count") or 0) + 1

    error_rate = 0.0
    quality_trend = "stable"
    score_trend = 0.0
    quality_drift_detected = False

    # 3. Retrieve historical context for trend & error rate calculation
    if pipeline_id and organization_id:
        try:
            async with AsyncSessionLocal() as session:
                repo = EvaluationRepository(session)
                historical_runs = await repo.list_by_pipeline(
                    pipeline_id=uuid.UUID(pipeline_id),
                    organization_id=uuid.UUID(organization_id),
                    limit=50,
                )

                # Compute rolling error rate (runs in failed/blocked status)
                if historical_runs:
                    failed_count = sum(
                        1 for r in historical_runs if r.status in ("failed", "blocked")
                    )
                    error_rate = failed_count / len(historical_runs)

                # Compute quality trend compared to the last completed evaluation run
                completed_runs = [
                    r
                    for r in historical_runs
                    if r.status == "completed" and str(r.run_id) != run_id
                ]
                if completed_runs:
                    prev_score = float(completed_runs[0].unified_score or 0.0)
                    score_trend = unified_score - prev_score

                    if score_trend > 0.01:
                        quality_trend = "improving"
                    elif score_trend < -0.01:
                        quality_trend = "degrading"
                    else:
                        quality_trend = "stable"

                # G-6: Quality drift — sustained multi-run decline distinct from
                # the acute -0.10 rollback threshold.  Window = 5 most recent
                # completed runs (DESC order from repo, index 0 = most recent).
                window = completed_runs[:5]
                if len(window) >= 3:
                    declining_pairs = sum(
                        1
                        for i in range(len(window) - 1)
                        if float(window[i].unified_score or 0.0)
                        < float(window[i + 1].unified_score or 0.0)
                    )
                    total_drift = float(window[0].unified_score or 0.0) - float(
                        window[-1].unified_score or 0.0
                    )
                    quality_drift_detected = (
                        declining_pairs >= 2 and total_drift < -0.05
                    )
                else:
                    quality_drift_detected = False
        except Exception as exc:
            quality_drift_detected = False
            logger.error(
                "observer_node_db_query_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

    # 4. Check thresholds and set alert flags
    alert_triggered = False
    alerts_fired: list[str] = []

    # Check p95 latency threshold (> 3000ms)
    if latency_p95_ms > 3000:
        alert_triggered = True
        alerts_fired.append("latency_p95_breach")
        logger.warning(
            "Observer: Latency threshold breached",
            extra={
                "metric": "latency_p95_ms",
                "value": latency_p95_ms,
                "threshold": 3000,
                "x_trace_id": x_trace_id,
            },
        )
        logger.warning(
            "Webhook event 'agent.health_degraded' emitted",
            extra={
                "event_type": "agent.health_degraded",
                "pipeline_id": pipeline_id,
                "metric": "latency_p95_ms",
                "value": latency_p95_ms,
                "threshold": 3000,
                "x_trace_id": x_trace_id,
            },
        )

    # Check rolling error rate threshold (> 1%)
    if error_rate > 0.01:
        alert_triggered = True
        alerts_fired.append("error_rate_breach")
        logger.warning(
            "Observer: Error rate threshold breached",
            extra={
                "metric": "error_rate",
                "value": error_rate,
                "threshold": 0.01,
                "x_trace_id": x_trace_id,
            },
        )
        logger.warning(
            "Webhook event 'agent.health_degraded' emitted",
            extra={
                "event_type": "agent.health_degraded",
                "pipeline_id": pipeline_id,
                "metric": "error_rate",
                "value": error_rate,
                "threshold": 0.01,
                "x_trace_id": x_trace_id,
            },
        )

    # Check score drop trend (> 0.10 drop)
    if score_trend < -0.10:
        alert_triggered = True
        alerts_fired.append("score_drop_breach")
        logger.warning(
            "Observer: Unified score trend drop breached",
            extra={
                "metric": "unified_score_trend",
                "value": score_trend,
                "threshold": -0.10,
                "x_trace_id": x_trace_id,
            },
        )
        logger.warning(
            "Webhook event 'agent.health_degraded' emitted",
            extra={
                "event_type": "agent.health_degraded",
                "pipeline_id": pipeline_id,
                "metric": "unified_score_trend",
                "value": score_trend,
                "threshold": -0.10,
                "x_trace_id": x_trace_id,
            },
        )

    # Check quality drift (sustained multi-run decline — G-6 / F-06)
    if quality_drift_detected:
        alert_triggered = True
        alerts_fired.append("quality_drift_detected")
        logger.warning(
            "Observer: Quality drift detected across window of completed runs",
            extra={
                "metric": "quality_drift",
                "quality_trend": quality_trend,
                "score_trend": score_trend,
                "x_trace_id": x_trace_id,
            },
        )
        logger.warning(
            "Webhook event 'agent.quality_drift' emitted",
            extra={
                "event_type": "agent.quality_drift",
                "pipeline_id": pipeline_id,
                "x_trace_id": x_trace_id,
            },
        )

    # Check cost threshold (exceeds environment ceiling)
    if cost_per_query_usd > settings.max_query_cost_usd:
        alert_triggered = True
        alerts_fired.append("cost_ceiling_breach")
        logger.warning(
            "Observer: Cost per query threshold breached",
            extra={
                "metric": "cost_per_query_usd",
                "value": cost_per_query_usd,
                "threshold": settings.max_query_cost_usd,
                "x_trace_id": x_trace_id,
            },
        )
        logger.warning(
            "Webhook event 'cost.threshold_exceeded' emitted",
            extra={
                "event_type": "cost.threshold_exceeded",
                "pipeline_id": pipeline_id,
                "cost_usd": cost_per_query_usd,
                "ceiling_usd": settings.max_query_cost_usd,
                "x_trace_id": x_trace_id,
            },
        )

        # Write to audit_log (event_type: cost_limit_exceeded)
        if organization_id:
            try:
                async with AsyncSessionLocal() as session:
                    audit_repo = AuditLogRepository(session)
                    await audit_repo.insert(
                        event_type="cost_limit_exceeded",
                        payload={
                            "cost_usd": cost_per_query_usd,
                            "ceiling_usd": settings.max_query_cost_usd,
                        },
                        organization_id=uuid.UUID(organization_id),
                        run_id=uuid.UUID(run_id) if run_id else None,
                        trace_id=x_trace_id,
                    )
                    await session.commit()
            except Exception as exc:
                logger.error(
                    "observer_node_audit_log_insert_failed",
                    extra={"error": str(exc), "x_trace_id": x_trace_id},
                )

    # 5. Push to Prometheus metrics
    try:
        from app.metrics import AGENT_COST, AGENT_LATENCY, QUERY_COST

        AGENT_COST.labels(agent_name="observer", provider=provider).inc(0.0)
        AGENT_LATENCY.labels(agent_name="observer").observe(latency_p95_ms)
        QUERY_COST.labels(provider=provider).set(cost_per_query_usd)
    except Exception as exc:
        logger.error(
            "observer_node_prometheus_push_failed",
            extra={"error": str(exc), "x_trace_id": x_trace_id},
        )

    # 6. Trigger auto-rollback if error_rate > 1% or p95 > 3s
    deployment_decision = state.get("deployment_decision")
    deploy_status = state.get("deploy_status")
    rollback_reason = state.get("rollback_reason")

    if error_rate > 0.01 or latency_p95_ms > 3000:
        rollback_reason = f"Observer triggered rollback: error_rate={error_rate:.2%} (threshold: 1%) or latency_p95_ms={latency_p95_ms}ms (threshold: 3000ms)"
        deployment_decision = "rollback"
        deploy_status = "rolled_back"

        # Write rollback_triggered to audit_log
        if organization_id:
            try:
                async with AsyncSessionLocal() as session:
                    audit_repo = AuditLogRepository(session)
                    await audit_repo.insert(
                        event_type="rollback_triggered",
                        payload={
                            "reason": rollback_reason,
                            "error_rate": error_rate,
                            "latency_p95_ms": latency_p95_ms,
                        },
                        organization_id=uuid.UUID(organization_id),
                        run_id=uuid.UUID(run_id) if run_id else None,
                        trace_id=x_trace_id,
                    )
                    await session.commit()
            except Exception as exc:
                logger.error(
                    "observer_node_rollback_audit_log_failed",
                    extra={"error": str(exc), "x_trace_id": x_trace_id},
                )

        # Trigger actual rollback via DeploymentService
        try:
            from app.services.deployment_service import DeploymentService

            async with AsyncSessionLocal() as _db:
                deploy_service = DeploymentService(_db)
                await deploy_service.rollback(
                    pipeline_id=pipeline_id,
                    organization_id=state.get("organization_id", ""),
                    rollback_reason="observer_auto_rollback",
                    x_trace_id=x_trace_id,
                )
        except Exception as exc:
            logger.error(
                "DeploymentService.rollback failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

    observation_flags = {
        "latency_breach": latency_p95_ms > 3000,
        "score_drop": score_trend < -0.10,
        "error_spike": error_rate > 0.01,
        "quality_drift": quality_drift_detected,
    }

    node_latency_ms = int((time.monotonic() - node_start) * 1000)
    trace_entry = {
        "node": "observer",
        "timestamp": datetime.now(UTC).isoformat(),
        "x_trace_id": x_trace_id,
        "graph_state_version": state.get("graph_state_version", "v1.0"),
        "latency_ms": node_latency_ms,
        "status": "success",
        "retry_count": retry_count,
        "cost_usd": 0.0,
        "provider": "none",
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }

    logger.info(
        "Observer node completed successfully",
        extra={
            "x_trace_id": x_trace_id,
            "error_rate": error_rate,
            "quality_trend": quality_trend,
            "alert_triggered": alert_triggered,
        },
    )

    return {
        **state,
        "error_rate": error_rate,
        "quality_trend": quality_trend,  # type: ignore[typeddict-item]
        "alert_triggered": alert_triggered,
        "deployment_decision": deployment_decision,
        "deploy_status": deploy_status,  # type: ignore[typeddict-item]
        "rollback_reason": rollback_reason,
        "observation_flags": observation_flags,
        "retry_count": retry_count,
        "execution_trace": [*existing_trace, trace_entry],
    }
