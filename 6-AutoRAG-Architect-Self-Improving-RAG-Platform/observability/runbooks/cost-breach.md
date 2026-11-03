# Runbook: Cost Budget Breach

**Alert**: `AgentCostSpike`
**Severity**: High
**Auto-rollback**: No — but blocks new deployments until HITL reviewed
**Owner**: Team 3 (MLflow) + Team 10 (Platform)

---

## Trigger Conditions

- `sum(increase(autorag_agent_cost_usd_total[24h])) > 2 * 7-day baseline`
- `autorag_cost_per_query_usd > MAX_QUERY_COST_USD` env var value
- `CostGuardrail.check()` returns `exceeded=True` in `app/services/cost_guardrail.py`

---

## Symptoms

- Grafana: Daily cost bar chart shows spike > 2× last 7-day average
- `audit_log` contains entries with `event_type = cost_limit_exceeded`
- Improver Agent blocked: `CostGuardrail.check()` returns exceeded before generating variants
- (No live `/cost` dashboard page exists — Cost Analytics was removed from
  primary nav 12-Jul-2026 for fabricating its entire dataset; use the Grafana
  cost panels above instead — see `verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md`)

---

## Diagnosis Steps

### Step 1 — Identify which agent is expensive
```
sum by (agent_name) (increase(autorag_agent_cost_usd_total[24h]))
```
The most expensive agents are typically: `builder` (embeddings), `evaluator` (judge calls), `improver` (variant generation).

### Step 2 — Check token explosion
```
sum by (agent_name, token_type) (increase(autorag_agent_tokens_total[24h]))
```
High `prompt_tokens` on `compressor` → context window not being compressed correctly.
High `completion_tokens` on `evaluator` → judge prompts returning verbose explanations.

### Step 3 — Check provider failover cost
KiMi K2.6 fallback costs 33% more per token than Gemini Flash 3.5. If failover is frequent:
```
autorag_provider_switch_total{from_provider="gemini-flash-3.5", to_provider="kimi-k2.6"}
```

### Step 4 — Check Improver variant count
The Improver generates exactly 3 variants per run, hardcoded in
`app/graph/nodes/improver.py` (no `MAX_VARIANTS` env var exists to raise this)
— check the MLflow experiment run's logged variant runs for cost, not count.

---

## Resolution

| Root Cause | Action |
|------------|--------|
| Token explosion | Reduce `MAX_CONTEXT_TOKENS` env var; check `TokenGuardrail` in `app/services/token_guardrail.py` |
| Provider failover | Fix root cause of primary provider failures (see high-latency.md) |
| Improver variant cost too high | Variant count is fixed at 3 (no env override); check `autorag-server/config/production/slo.yaml` cost_budgets |
| Budget env var too low for workload | Raise `MAX_EVAL_COST_USD` after Mahesh Kumar approval |

### Emergency cost cap
To immediately cap all LLM spending (sets `cost_limit_exceeded` state):
```bash
# Set hard cap in environment -- requires ECS task restart
aws ssm put-parameter --name /autorag/prod/MAX_QUERY_COST_USD --value 0.005 --overwrite
aws ecs update-service --cluster autorag-production --service autorag-api --force-new-deployment
```

---

## Escalation

- Daily cost > 5× baseline: Page Mahesh Kumar immediately
- `max_monthly_cost_increase_pct` exceeded: HITL required — Mahesh Kumar both approve
- Billing alert from AWS: Open cost incident in audit_log

---

## Post-Incident

1. Write `audit_log` entry: `event_type = cost_limit_exceeded`, include provider + amount
2. Update `config/production/slo.yaml` `cost_budgets` section if thresholds were wrong
3. Log MLflow metric `cost_per_query_usd` for the incident run
4. Review `autorag-server/config/model_pricing.yaml` for accuracy if provider changed pricing
