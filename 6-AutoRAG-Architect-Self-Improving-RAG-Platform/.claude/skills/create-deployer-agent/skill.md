# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Deployer Agent Skill

## Purpose

Implement the AutoRAG **Deployer Agent** (Agent 9 in the 9-agent loop). This agent executes Blue/Green ECS Fargate deployments, performs ALB target weight swaps, monitors the 10-minute canary window, and triggers auto-rollback on threshold breach.

---

## When to Use

- Adding or modifying the Deployer LangGraph node
- Changing deployment gate logic (Unified Score threshold, canary window)
- Implementing or updating rollback trigger conditions
- Writing integration tests for deploy → canary → rollback graph paths

---

## Deployment Prerequisites (all must pass before deploy proceeds)

| Gate                     | Threshold        | Enforcement                          |
| ------------------------ | ---------------- | ------------------------------------ |
| Unified Score            | >= 0.85          | Hard block — non-bypassable          |
| Faithfulness             | >= 0.5           | Hard block — non-bypassable          |
| Adversarial Pass Rate    | 100%             | Hard block — fabricated answer = fail|
| Manual Approval          | Named signoff    | Mahesh Kumar / Lead DevOps       |
| Docker image tag         | Immutable SHA    | No `latest` tags allowed in ECS      |

---

## GraphState Input Fields

```python
class DeployerInput(TypedDict):
    run_id: str                  # UUID v7
    x_trace_id: str              # propagated from request boundary
    pipeline_id: str             # pipeline being deployed
    pipeline_version: str        # e.g. "v1.3"
    unified_score: float         # must be >= 0.85
    ecr_image_uri: str           # full SHA-tagged ECR URI
    approval_token: str          # signed approval from HITL gate
    blue_task_arn: str           # currently active ECS task definition ARN
    green_task_arn: str          # new task definition to promote
```

## GraphState Output Fields

```python
class DeployerOutput(TypedDict):
    deploy_status: str           # "success" | "rolled_back" | "failed"
    active_task_arn: str         # ARN of task now serving 100% traffic
    alb_weight_blue: int         # 0 or 100
    alb_weight_green: int        # 0 or 100
    rollback_reason: str | None  # populated if rolled_back
    x_trace_id: str              # propagated unchanged
```

---

## Deployment Flow

```
Score Gate Check (>= 0.85)
        ↓
Approval Gate Verify
        ↓
ECS Green Task Register
        ↓
ALB Weight: Blue 90 / Green 10  (canary start)
        ↓
10-Minute Canary Monitor
        ↓
   [Pass]              [Fail]
     ↓                   ↓
ALB 0/100          Auto-Rollback → ALB 100/0
(Green live)       (Blue restored)
        ↓
webhook: workflow.completed (success) -- audit_log: rollback_triggered (on rollback)
```

---

## Rollback Trigger Conditions (any one = immediate rollback)

- `error_rate > 1%` in canary window
- `p95 latency > 3000ms` in canary window
- `Unified Score drop > 0.10` vs pre-deploy baseline

---

## Implementation Pattern

```python
# autorag-server/app/graph/nodes/deployer.py
async def deployer_node(state: GraphState) -> GraphState:
    """
    Executes Blue/Green ECS deploy and monitors canary window.
    Stateless — all state in GraphState.
    Score gate is checked here as final defense; Evaluator also enforces it.
    """
    # Hard score gate — non-bypassable
    if state["unified_score"] < 0.85:
        raise DeploymentBlockedError(
            f"Unified Score {state['unified_score']} < 0.85 — deployment blocked"
        )

    await ecs_service.register_green_task(state["green_task_arn"])
    await alb_service.set_weights(blue=90, green=10, x_trace_id=state["x_trace_id"])

    rollback_reason = await canary_monitor.watch(
        duration_seconds=600,
        thresholds={"error_rate": 0.01, "p95_ms": 3000, "score_drop": 0.10},
        x_trace_id=state["x_trace_id"],
    )

    if rollback_reason:
        await alb_service.set_weights(blue=100, green=0, x_trace_id=state["x_trace_id"])
        deploy_status = "rolled_back"
        active_arn = state["blue_task_arn"]
    else:
        await alb_service.set_weights(blue=0, green=100, x_trace_id=state["x_trace_id"])
        deploy_status = "success"
        active_arn = state["green_task_arn"]

    if deploy_status == "rolled_back":
        # rollback_triggered is one of the 13 real APPROVED_EVENT_TYPES
        await audit_log.insert(
            event_type="rollback_triggered",
            run_id=state["run_id"],
            x_trace_id=state["x_trace_id"],
            payload={"status": deploy_status, "active_arn": active_arn, "reason": rollback_reason},
        )
    await webhook_dispatcher.emit(
        "workflow.completed",
        pipeline_id=state["pipeline_id"], run_id=state["run_id"],
        active_task_arn=active_arn, x_trace_id=state["x_trace_id"],
    )

    return {**state, "deploy_status": deploy_status, "active_task_arn": active_arn,
            "rollback_reason": rollback_reason}
```

---

## Safety Checklist

See `checklists/deployment-safety.md` for the full pre-deploy verification checklist.

Key invariants:
- Docker image tags must be immutable SHA (never `latest`)
- AWS Secrets Manager — never inline secrets in ECS task definition YAML
- `audit_log` INSERT ONLY — log deploy + rollback events; never UPDATE or DELETE
- New version's chunks written into the shared `pipeline_chunks` table under a new `pipeline_version` before deploy; old version's rows never mutated (Version 4.0, migration 0016)
- Terraform manages all ECS/ALB config — no console or CLI ad-hoc changes

---

## Tests Required

- Unit test: Unified Score < 0.85 raises `DeploymentBlockedError` before any ECS call
- Integration test: successful canary → ALB weight swap to Green (mocked ECS + ALB)
- Integration test: error_rate breach → rollback → Blue restored within 10 minutes
- Integration test: `audit_log` receives exactly 1 INSERT per deploy/rollback event
- E2E test: full Evaluator → Approver → Deployer graph path in staging environment
