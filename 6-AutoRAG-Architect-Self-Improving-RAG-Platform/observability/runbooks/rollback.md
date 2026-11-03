# Runbook: ECS Blue/Green Rollback

**Alert**: Any critical SLO breach during 10-minute canary window
**Severity**: Critical
**Trigger**: Auto-rollback fires OR manual decision by Mahesh Kumar
**Owner**: Team 1 (DevOps) + Team 10 (Platform)

---

## Auto-Rollback Conditions (Deployer Agent)

Auto-rollback fires within the 10-minute canary window if ANY of:
- `error_rate > 1%` (5xx responses)
- `p95 latency > 3s`
- `Unified Score drop > 0.10` vs pre-deploy baseline

---

## Pre-Rollback Checklist

Before triggering manual rollback, verify:

- [ ] Alert is not a false positive (check 2+ data points in Grafana)
- [ ] Auto-rollback has not already fired (check `audit_log` for `event_type = rollback_triggered`, or `deployments.status = rolled_back`)
- [ ] Active task ARN is recorded (Deployer Agent stores in `GraphState.active_task_arn`)
- [ ] Checkpoint exists for the pre-deploy state

---

## Automatic Rollback (Deployer Agent)

The Deployer Agent handles rollback via LangGraph edge `_route_after_observer()`:

1. Observer detects SLO breach
2. Routes to Diagnoser (classifies failure)
3. Routes to Deployer with `rollback=True`
4. Deployer calls ECS `update-service` to restore previous task definition

Monitor in CloudWatch:
```bash
aws logs filter-log-events \
  --log-group-name /autorag/production \
  --filter-pattern "rollback" \
  --start-time $(date -d '30 minutes ago' +%s000)
```

---

## Manual Rollback Procedure

### Step 1 — Get the previous task definition ARN
```bash
# List last 5 task definition revisions
aws ecs list-task-definitions \
  --family-prefix autorag-api \
  --sort DESC \
  --max-items 5 \
  --query 'taskDefinitionArns'
```

### Step 2 — Trigger rollback to previous revision
```bash
PREV_TASK_DEF="arn:aws:ecs:ap-south-1:ACCOUNT:task-definition/autorag-api:PREV_REV"

aws ecs update-service \
  --cluster autorag-production \
  --service autorag-api \
  --task-definition "$PREV_TASK_DEF" \
  --force-new-deployment
```

### Step 3 — Monitor deployment
```bash
aws ecs wait services-stable \
  --cluster autorag-production \
  --services autorag-api autorag-workers
```

### Step 4 — Verify health
```bash
# Health check
curl https://api.autorag-architect.com/health
curl https://api.autorag-architect.com/api/v1/health

# Smoke test: run one query and check score
curl -X POST https://api.autorag-architect.com/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the Unified Score gate?", "pipeline_id": "<current_pipeline>"}'
```

---

## Rollback for LangGraph Workers

If workers (not API) need rollback:
```bash
aws ecs update-service \
  --cluster autorag-production \
  --service autorag-workers \
  --task-definition "arn:aws:ecs:ap-south-1:ACCOUNT:task-definition/autorag-workers:PREV_REV" \
  --force-new-deployment
```

Note: Workers use immutable SHA image tags (never `latest`). The previous task definition already points to the correct ECR image SHA.

---

## Post-Rollback Steps

1. **Verify Unified Score recovery**: Run `POST /api/v1/evaluate` and confirm score >= 0.85
2. **Write audit log entry**: `event_type = rollback_triggered` (the real approved
   type — `app/models/audit_log.py`; there is no separate `rollback_completed`),
   include `rollback_reason`, `active_task_arn`, reviewer identity in `payload`
3. **Notify team**: Slack + WhatsApp (Wati) notification — no `POST /api/v1/notify`
   endpoint exists; this is dispatched by the Deployer node's own notification
   integration, not a standalone API call
4. **Root cause analysis**: Run Diagnoser Agent (`GET /api/v1/diagnose/{run_id}`) with the failed run ID
5. **Block re-deploy**: Do not re-deploy until root cause resolved and score >= 0.85 confirmed in staging

---

## Escalation

- Rollback does not recover SLO within 15 min: Page Mahesh Kumar
- Multiple rollbacks in 1 hour: Freeze all deployments, open incident
- Rollback task definition unavailable: Contact AWS support — immutable SHA tags prevent this but verify ECR retention policy
