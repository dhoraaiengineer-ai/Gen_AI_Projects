# Agent 9: Deployer

**Status**: Spec | **Phase**: F-2 | **Team**: Team 1 + Team 10

---

## Responsibility

Execute Blue/Green ECS Fargate deployments using ALB target group weight swaps. Monitor the 10-minute canary window and auto-rollback if error rate, latency, or Unified Score thresholds breach. Emit webhook events on completion or rollback.

---

## Input Schema

```python
class DeployerInput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    approval_decision: Literal["auto", "hitl_approved"]
    approver_id: str | None      # required if hitl_approved
    ecr_image_uri: str           # immutable SHA tag — never "latest"
    target_environment: Literal["staging", "production"]
    rollback_image_uri: str      # current running image — kept on standby
    canary_window_minutes: int = 10
    x_trace_id: str
```

---

## Output Schema

```python
class DeployerOutput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    deployment_status: Literal["deployed", "rolled_back", "failed"]
    ecs_task_arn: str            # deployed task definition ARN
    alb_target_group_arn: str
    canary_passed: bool
    canary_metrics: CanaryMetrics
    rollback_triggered: bool
    rollback_reason: str | None
    x_trace_id: str

class CanaryMetrics(BaseModel):
    error_rate_pct: float
    latency_p95_ms: float
    unified_score_delta: float   # vs. pre-deploy baseline
    observation_window_minutes: int
```

---

## Deployment Procedure

1. Push new ECS task definition with immutable SHA image tag
2. Register new target group version (Green)
3. Shift ALB weight: Blue 90% → Green 10%
4. Monitor canary for `canary_window_minutes`
5. If canary passes: shift ALB weight to Green 100% → Blue 0%
6. If canary fails: shift ALB weight back to Blue 100%; deregister Green
7. Write audit_log entry for every weight shift and final outcome

---

## Auto-Rollback Triggers (Canary Window)

| Metric                | Threshold     | Action                     |
| --------------------- | ------------- | -------------------------- |
| `error_rate_pct`      | `> 1%`        | Immediate rollback to Blue |
| `latency_p95_ms`      | `> 3000ms`    | Immediate rollback to Blue |
| `unified_score_delta` | Drop `> 0.10` | Immediate rollback to Blue |

---

## Failure Modes

| Failure                                  | Classification | Retry Policy                                                    |
| ---------------------------------------- | -------------- | --------------------------------------------------------------- |
| ECS task definition registration failure | Transient      | Retry once; if fails, halt and alert                            |
| ALB target group registration failure    | Transient      | Retry once; rollback to Blue                                    |
| Canary threshold breach                  | Expected       | Automatic rollback — not a failure, expected path               |
| Rollback failure                         | Critical       | Emit `agent.health_degraded`; page Mahesh Kumar immediately |
| Missing `ecr_image_uri` SHA tag          | Validation     | Hard block — never deploy without immutable tag                 |

---

## Telemetry Emitted

| Event                           | When                               | Fields                                                           |
| ------------------------------- | ---------------------------------- | ---------------------------------------------------------------- |
| `workflow.completed` webhook    | Successful full deployment         | `pipeline_id`, `run_id`, `ecs_task_arn`, `x_trace_id`            |
| `agent.health_degraded` webhook | Rollback triggered                 | `pipeline_id`, `rollback_reason`, `canary_metrics`, `x_trace_id` |
| Structured log (INFO)           | Each ALB weight shift              | `blue_weight`, `green_weight`, `x_trace_id`                      |
| Structured log (WARN)           | Canary threshold breach            | `metric`, `value`, `threshold`, `x_trace_id`                     |
| `audit_log` INSERT              | Every weight shift + final outcome | `action`, `actor`, `payload`, `timestamp`                        |

---

## Dependencies

- AWS ECS Fargate API (task definition registration, service update)
- AWS ALB API (target group weight shift)
- AWS ECR (image tag validation — rejects `latest`)
- Observer agent (canary metrics during window)
- SendGrid + Twilio (rollback alert notification to Mahesh Kumar)
- PostgreSQL `deployments` table + `audit_log` table
