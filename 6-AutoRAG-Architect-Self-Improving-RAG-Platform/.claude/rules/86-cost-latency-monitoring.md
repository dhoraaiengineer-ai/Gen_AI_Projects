# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 86: Agent Cost & Latency Monitoring

## Enforces:

1. **Capture**: Every LLM call MUST record `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, `provider`, and `x_trace_id` in the agent's `execution_trace` entry.

2. **Single cost source**: Cost calculation happens **only** in `autorag-server/app/services/llm_service.py`. Agent nodes MUST NOT calculate token cost independently.

3. **Trace naming**: The field MUST be `x_trace_id` — not `trace_id`. Consistent with all 76 GraphState fields and the API boundary header.

4. **PII safety**: No query text, user input, document content, or PII in metric records. Mask before persisting — Rule 70 + graph-state-governance Rule 6.

5. **GraphState discipline**: Do NOT add a parallel `agent_metrics` list to `GraphState`. Extend existing `execution_trace` entries with cost fields instead. A new GraphState field requires Architecture Review (frozen contract).

6. **MLflow telemetry**: Every evaluation run MUST log `cost_per_query_usd`, `latency_p95_ms`, `unified_score`, `total_tokens`, and `llm_provider_used` to MLflow. Owned by Team 3, Task E-3.

7. **Prometheus export**: Agent metrics MUST be exported as:
   - `autorag_agent_cost_usd_total{agent_name, provider}`
   - `autorag_agent_latency_ms{agent_name}` (histogram)
   - `autorag_agent_tokens_total{agent_name, provider, token_type}`
   - `autorag_cache_hits_total{agent_name}`, `autorag_cache_misses_total{agent_name}`, `autorag_cache_latency_ms{agent_name}`
   - `autorag_provider_failures_total{provider}`, `autorag_provider_switch_total{from_provider, to_provider}`
   - `autorag_provider_rate_limit_total{provider}`, `autorag_provider_timeout_total{provider}`

8. **Budget enforcement**: `CostGuardrail` in `app/services/cost_guardrail.py` is the single enforcement point. Improver Agent MUST call it before generating variants. Observer MUST trigger `cost.threshold_exceeded` webhook on breach.

9. **Token enforcement**: `TokenGuardrail` in `app/services/token_guardrail.py` guards context expansion. Improver MUST call it before increasing chunk size, context window, or `max_prompt_tokens`. Limits sourced from `config/token_budgets.yaml`.

10. **Audit trail**: Cost limit violations MUST be written to `audit_log` (INSERT-only — event type: `cost_limit_exceeded`).

11. **Schema governance**: The `agent_metrics` table is NOT in `DB_SCHEMA.md` v1.0 (frozen). Architecture Review is required before migration is applied. Until then, use `evaluation_runs.cost_usd` as stopgap.

12. **Configurable pricing**: Provider pricing MUST be loaded from `config/model_pricing.yaml` at startup — never hardcoded in Python. This avoids code deploys for pricing updates.

13. **Environment-specific budgets**: Cost budget constants MUST be loaded from environment variables — not hardcoded in `CostBudget` class. See env var table below.

## Cost Budget Env Vars (per environment)

| Env Var | Dev | Staging | Prod | Notes |
|---------|-----|---------|------|-------|
| `MAX_QUERY_COST_USD` | 0.05 | 0.02 | 0.01 | Per single query |
| `MAX_EVAL_COST_USD` | 1.00 | 0.75 | 0.60 | Per evaluation run |
| `MAX_PIPELINE_BUILD_USD` | 5.00 | 3.00 | 2.00 | Per full pipeline build |
| `MAX_MONTHLY_COST_INCREASE_PCT` | 0.50 | 0.30 | 0.20 | HITL required above |
| `MAX_PROMPT_TOKENS` | 32000 | 32000 | 32000 | TokenGuardrail limit |
| `MAX_COMPLETION_TOKENS` | 4096 | 4096 | 4096 | TokenGuardrail limit |
| `MAX_CONTEXT_TOKENS` | 64000 | 64000 | 64000 | TokenGuardrail limit |

## Unified Score Reminder

Cost is a **5% penalty factor** in the deployment gate:

```
Score = 0.25×Recall + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost
```

High-cost pipelines directly reduce deployment eligibility. Monitor cost not just for budget but for score health.

## Anti-Patterns:

- Agent nodes computing `cost_usd = prompt_tokens * rate` themselves.
- Using `trace_id` instead of `x_trace_id`.
- Logging raw user queries alongside cost metrics (PII violation).
- Adding `agent_metrics: List[AgentMetric]` to GraphState without Architecture Review.
- Deploying without Prometheus metrics wired — Observer Agent requires them for auto-rollback decisions.
- Improver generating variants without calling `CostGuardrail.check()` and `TokenGuardrail.check()`.
- Hardcoding provider pricing rates in Python — use `config/model_pricing.yaml`.
- Hardcoding `MAX_QUERY_COST_USD` constants in Python — use env vars per environment.

## Reference:

Full implementation guide: [`docs/AGENT_COST_AND_LATENCY_GUIDE.md`](../docs/AGENT_COST_AND_LATENCY_GUIDE.md)
