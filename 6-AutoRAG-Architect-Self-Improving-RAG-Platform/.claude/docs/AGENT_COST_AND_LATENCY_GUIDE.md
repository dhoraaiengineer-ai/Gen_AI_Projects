# Agent Cost & Latency Monitoring Implementation Guide

**Version:** 1.1
**Status:** Mandatory Implementation Guide — AutoRAG v3.0 Aligned
**Owner:** Team 1 (Observer Agent + Grafana) | Team 3 (LLM Service + MLflow) | Team 2 (Evaluator)
**Date:** June 2026
**Supersedes:** v1.0 draft

---

## 1. Purpose

This document defines the implementation standards for measuring, storing, monitoring, and visualizing:

1. LLM Token Consumption
2. LLM API Cost
3. Agent Response Latency
4. Cost vs Quality Tradeoffs
5. Cost Budget Enforcement
6. Production Cost Monitoring

Every LLM invocation in AutoRAG MUST expose:

| Field | Type | Notes |
|-------|------|-------|
| `prompt_tokens` | int | Input token count |
| `completion_tokens` | int | Output token count |
| `total_tokens` | int | Sum |
| `cost_usd` | float | Calculated in `llm_service.py` only |
| `provider` | str | `gemini-flash-3.5` \| `kimi-k2.6` \| `gemini-3.5` |
| `latency_ms` | int | Wall-clock ms from call start to return |
| `retry_count` | int | Number of failover retries |
| `x_trace_id` | UUID | Propagated unchanged from API boundary |

This information is required for:

- Unified Score calculation (cost is a 5% penalty factor)
- Cost budget enforcement via `CostGuardrail`
- Observer Agent monitoring and auto-rollback
- MLflow experiment tracking
- Grafana production dashboards
- Monthly cost forecasting

---

## 2. Ownership Matrix

| Team | Responsibility |
|------|----------------|
| Team 2 | Evaluator Agent + Unified Score cost integration |
| Team 3 | LLM Service wrapper + MLflow telemetry (Task E-3) |
| Team 1 | Observer Agent + Prometheus instrumentation + Grafana dashboards |
| Team 6 | Vector Retrieval latency metrics (Builder/Retriever nodes) |
| Team 10 | Deployment cost dashboards + ECS rollback triggers |

> **Note:** "Observability" in this document refers to the monitoring stack owned by Team 1 (Observer Agent, Prometheus, Grafana). Team 6 owns vector retrieval — not the observability platform.

---

## 3. Metrics to Capture Per LLM Call

Every agent node that calls the LLM MUST record the following structure. This is appended to `execution_trace` — **not** a separate GraphState field.

```python
# Appended to state["execution_trace"] by every agent node after LLM call
{
    "node": "query_rewriter",            # agent name — matches LangGraph node name
    "timestamp": "2026-06-17T10:22:11Z", # ISO 8601 UTC
    "x_trace_id": "018ece7c-...",        # NOT trace_id — must match GraphState field name
    "graph_state_version": "v1.0",
    "latency_ms": 748,
    "status": "success",                 # success | error | timeout | guardrail_blocked
    "retry_count": 0,
    # Cost fields — populated by LLMService, never by agent nodes directly
    "cost_usd": 0.00014,
    "provider": "gemini-flash-3.5",      # reflects state.llm_provider_used
    "prompt_tokens": 120,
    "completion_tokens": 35,
    "total_tokens": 155
}
```

**PII Rule (mandatory):** No query text, user input, document content, or any PII may appear in this record. Mask first, log second — Rule 70 + graph-state-governance Rule 6.

---

## 4. Agents Requiring Monitoring

### Agent 1 — Ingestion

Track: embedding tokens, embedding API cost, chunking duration, Supabase Storage upload time.

| Metric | Target |
|--------|--------|
| Total latency | 30–90 sec |
| Embedding cost | < $1.50 |
| Chunking time | < 20 sec |
| Embedding time | < 60 sec |

---

### Agent 2 — Query Rewriter

Track: prompt tokens, completion tokens, cost, rewrite latency.

| Metric | Target |
|--------|--------|
| Latency | < 100 ms |
| Cost | < $0.0002 |
| Retries | 0 |

---

### Agent 3 — Builder

Track: embedding cost, BM25 latency, vector insertion time, Cohere Rerank cost, HyDE cost.

| Metric | Target |
|--------|--------|
| Total latency | 1–3 min |
| Cost | < $2.00 |
| Embedding | < 90 sec |
| Vector insert | < 30 sec |

---

### Agent 4 — Context Compressor

Track: compression ratio, compression latency, LLM tokens, cost.

| Metric | Target |
|--------|--------|
| Latency | < 150 ms |
| Cost | < $0.0005 |
| Compression ratio | > 40% |

---

### Agent 5 — Evaluator

Track: total evaluation tokens, judge LLM cost, RAGAS duration, adversarial test duration.

| Metric | Target |
|--------|--------|
| Total runtime | < 8 min |
| Cost | < $0.60 |
| RAGAS | < 2 min |
| Adversarial | < 30 sec |

---

### Agent 6 — Observer

Track: daily cost, monthly projected cost, token consumption, cost per query, quality trends.

| Metric | Target |
|--------|--------|
| Dashboard refresh | 30 sec |
| Alert latency | < 1 min |

---

### Agent 7 — Diagnoser

Track: diagnosis latency, LLM cost, failure classification.

| Metric | Target |
|--------|--------|
| Latency | < 2 sec |
| Cost | < $0.005 |

---

### Agent 8 — Improver

Track: variants generated, total variant cost, improvement delta, retry count.

| Metric | Target |
|--------|--------|
| Runtime | < 20 min |
| Cost | < $0.20 |
| Variants | 3–5 |

---

### Agent 9 — Deployer

Track: ECS deployment duration, rollback count, health check latency.

| Metric | Target |
|--------|--------|
| Deploy | < 10 min |
| Rollback | < 60 sec |

---

## 5. Database Schema

> ✅ **Approved and live** — ADR-006 approved 02-Jul-2026, migration `0006_add_agent_metrics.py`
> applied 03-Jul-2026. `agent_metrics` is a real, live table (F-12 ✅ DONE). The stopgap language
> below (using `evaluation_runs.cost_usd` until approval) described the pre-approval state and no
> longer applies -- corrected 24-Jul-2026 audit, see `adr/006-agent-metrics-table.md`.

```sql
-- Alembic migration: autorag-server/migrations/versions/0006_add_agent_metrics.py
-- upgrade() body:

CREATE TABLE agent_metrics (
    id                UUID PRIMARY KEY,           -- uuid_utils.uuid7() at app layer
    organization_id   UUID NOT NULL REFERENCES organizations(id),  -- multi-tenancy mandatory
    run_id            UUID NOT NULL REFERENCES pipeline_runs(id),
    x_trace_id        UUID NOT NULL,             -- propagated from API boundary unchanged
    agent_name        VARCHAR(50)  NOT NULL,
    provider          VARCHAR(50)  NOT NULL,      -- gemini-flash-3.5 | kimi-k2.6 | gemini-3.5
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost_usd          NUMERIC(10,6),
    latency_ms        INTEGER,
    retry_count       INTEGER DEFAULT 0,
    status            VARCHAR(30),               -- success | error | timeout | guardrail_blocked
    metadata          JSONB,
    deleted_at        TIMESTAMPTZ,               -- soft-delete — Rule 30
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_metrics_org   ON agent_metrics(organization_id);
CREATE INDEX idx_agent_metrics_run   ON agent_metrics(run_id);
CREATE INDEX idx_agent_metrics_trace ON agent_metrics(x_trace_id);
CREATE INDEX idx_agent_metrics_name  ON agent_metrics(agent_name);
CREATE INDEX idx_agent_metrics_date  ON agent_metrics(created_at);
```

**Alembic migration file** (`autorag-server/alembic/versions/XXXX_add_agent_metrics.py`) must include both `upgrade()` and `downgrade()` — Rule 30.

---

## 6. GraphState — No New Field (Extend execution_trace)

**Decision: Option A — extend existing `execution_trace` entries.**

Do NOT add `agent_metrics: List[AgentMetric]` to `GraphState`. That would require an Architecture Review per `docs/GRAPH_STATE.md` (frozen contract).

Instead, every agent node appends the cost fields shown in Section 3 directly into its `execution_trace` entry. The authoritative GraphState cost fields that already exist:

```python
# Already in autorag-server/app/core/state.py — DO NOT duplicate
cost_per_query_usd: float        # aggregated at Evaluator node
latency_p95_ms: int              # aggregated at Observer node
llm_provider_used: Optional[str] # set by LLMService on every call
```

Aggregate cost summary formula (Evaluator computes from `execution_trace`):

```python
total_cost = sum(
    entry.get("cost_usd", 0.0)
    for entry in state["execution_trace"]
)
state["cost_per_query_usd"] = total_cost
```

---

## 7. LLM Service Instrumentation

Cost calculation happens **only** in `autorag-server/app/services/llm_service.py`. Agent nodes never compute cost independently.

### LLMResponse contract

```python
from dataclasses import dataclass

@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float          # calculated here — never in caller
    provider: str            # reflects which chain link fired
```

### Provider pricing — loaded from `config/model_pricing.yaml`

Provider pricing MUST NOT be hardcoded in Python. Load from `autorag-server/config/model_pricing.yaml` at application startup via `app/core/config.py`. This means pricing updates require no code deploy.

**Reference rates** (actual rates are in the YAML file — update there when providers change pricing):

| Provider | Input (per 1M tokens) | Output (per 1M tokens) | Priority |
|---|---|---|---|
| Gemini Flash 3.5 | ~$0.075 | ~$0.30 | Primary |
| KiMi K2.6 | ~$0.14 | ~$0.55 | Fallback 1 |
| Gemini 3.5 | ~$1.00 | ~$5.00 | Fallback 2 (last resort) |

```python
# autorag-server/app/services/llm_service.py (skeleton)
# Rates loaded from config/model_pricing.yaml — NOT hardcoded here
from app.core.config import settings

def _calculate_cost(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = settings.model_pricing[provider]  # loaded from model_pricing.yaml
    return (
        prompt_tokens     * rates["input_per_million"]  / 1_000_000
        + completion_tokens * rates["output_per_million"] / 1_000_000
    )
```

`state.llm_provider_used` must be set to the provider string on every successful call so Observer and Evaluator can attribute cost correctly.

---

## 8. MLflow Cost & Latency Logging

Every pipeline evaluation run MUST log to MLflow. This is owned by **Team 3, Task E-3** (`feature/mlflow-telemetry`).

```python
# autorag-server/app/services/evaluator/mlflow_logger.py
import mlflow
from app.core.state import GraphState

async def log_run_to_mlflow(state: GraphState) -> None:
    total_tokens = sum(
        e.get("total_tokens", 0) for e in state["execution_trace"]
    )
    with mlflow.start_run(
        run_name=f"pipeline_{state['pipeline_id']}",
        experiment_id=settings.mlflow_experiment,
    ):
        mlflow.log_metrics({
            "cost_per_query_usd": state.get("cost_per_query_usd", 0.0),
            "latency_p95_ms":     state.get("latency_p95_ms", 0),
            "unified_score":      state.get("unified_score", 0.0),
            "total_tokens":       total_tokens,
        })
        mlflow.log_params({
            "llm_provider_used": state.get("llm_provider_used", "unknown"),
            "pipeline_id":       state["pipeline_id"],
            "organization_id":   state["organization_id"],
        })
```

Column references (already in schema): `experiment_runs.mlflow_run_id`, `experiment_runs.mlflow_experiment_id`.

---

## 9. Prometheus Metric Definitions

Define these in `autorag-server/app/metrics.py`. Names must match the scrape config in `observability/prometheus/prometheus.yml`.

```python
# autorag-server/app/metrics.py
from prometheus_client import Counter, Histogram

# --- Core agent metrics ---
AGENT_COST = Counter(
    "autorag_agent_cost_usd_total",
    "Cumulative LLM cost in USD",
    ["agent_name", "provider"],
)
AGENT_LATENCY = Histogram(
    "autorag_agent_latency_ms",
    "Agent LLM call latency in milliseconds",
    ["agent_name"],
    buckets=[50, 100, 200, 500, 1000, 2000, 3000, 5000],
)
AGENT_TOKENS = Counter(
    "autorag_agent_tokens_total",
    "Token consumption by agent and type",
    ["agent_name", "provider", "token_type"],  # token_type: prompt | completion
)

# --- Cache metrics (R-2) ---
CACHE_HITS = Counter(
    "autorag_cache_hits_total",
    "Redis cache hits by agent",
    ["agent_name"],
)
CACHE_MISSES = Counter(
    "autorag_cache_misses_total",
    "Redis cache misses by agent",
    ["agent_name"],
)
CACHE_LATENCY = Histogram(
    "autorag_cache_latency_ms",
    "Redis cache operation latency in milliseconds",
    ["agent_name"],
    buckets=[1, 5, 10, 25, 50, 100],
)

# --- Provider failover metrics (R-7) ---
PROVIDER_FAILURES = Counter(
    "autorag_provider_failures_total",
    "LLM provider failures by provider name",
    ["provider"],
)
PROVIDER_SWITCHES = Counter(
    "autorag_provider_switch_total",
    "LLM failover switches between providers",
    ["from_provider", "to_provider"],
)
PROVIDER_RATE_LIMITS = Counter(
    "autorag_provider_rate_limit_total",
    "LLM provider rate limit hits",
    ["provider"],
)
PROVIDER_TIMEOUTS = Counter(
    "autorag_provider_timeout_total",
    "LLM provider timeout events",
    ["provider"],
)
```

**Usage in Observer node** (`autorag-server/app/graph/nodes/observer.py`):

```python
from app.metrics import AGENT_COST, AGENT_LATENCY, AGENT_TOKENS

for entry in state["execution_trace"]:
    name = entry.get("node", "unknown")
    prov = entry.get("provider", "unknown")
    AGENT_COST.labels(agent_name=name, provider=prov).inc(entry.get("cost_usd", 0))
    AGENT_LATENCY.labels(agent_name=name).observe(entry.get("latency_ms", 0))
    AGENT_TOKENS.labels(agent_name=name, provider=prov, token_type="prompt").inc(
        entry.get("prompt_tokens", 0)
    )
    AGENT_TOKENS.labels(agent_name=name, provider=prov, token_type="completion").inc(
        entry.get("completion_tokens", 0)
    )
```

---

## 10. Observer Dashboard

### Grafana Panel Definitions

#### Cost Summary
- Daily cost: `sum(increase(autorag_agent_cost_usd_total[24h]))`
- Monthly projection: `sum(increase(autorag_agent_cost_usd_total[24h])) * 30`
- Cost by agent: `sum by(agent_name)(increase(autorag_agent_cost_usd_total[24h]))`
- Cost by provider: `sum by(provider)(increase(autorag_agent_cost_usd_total[24h]))`

#### Token Summary
- Daily tokens: `sum(increase(autorag_agent_tokens_total[24h]))`
- By type: `sum by(token_type)(increase(autorag_agent_tokens_total[24h]))`

#### Latency Dashboard (P50 / P95 / P99 per agent)
```promql
histogram_quantile(0.95, sum by(agent_name, le)(rate(autorag_agent_latency_ms_bucket[5m])))
```

#### Quality vs Cost Scatter
- X axis: `cost_per_query_usd` (from `evaluation_runs` table via Supabase datasource)
- Y axis: `unified_score`
- Goal: identify expensive low-performing pipelines

#### Model Efficiency Score (R-6)
```promql
# Efficiency = UnifiedScore / cost_per_query_usd
# Higher = better quality per dollar
```
Display as a table panel sorted descending — highlights which provider delivers best ROI.

#### Cache Hit Rate by Agent (R-2)
```promql
sum by(agent_name)(rate(autorag_cache_hits_total[5m]))
/ (sum by(agent_name)(rate(autorag_cache_hits_total[5m])) + sum by(agent_name)(rate(autorag_cache_misses_total[5m])))
```

#### Top Organizations by Cost (R-3)
- Group `evaluation_runs.cost_usd` by `organization_id` via Supabase datasource
- Panels: "Top 10 Orgs by Daily Cost", "Monthly Cost per Org", "Cost per Pipeline per Org"
- Required for SaaS billing and per-tenant cost governance

#### Provider Failover Dashboard (R-7)
- `autorag_provider_switch_total` — failover frequency by from/to provider pair
- `autorag_provider_failures_total` — failure rate per provider
- `autorag_provider_rate_limit_total` — rate limit events per provider
- Goal: identify unstable or expensive fallback paths

---

## 11. Alerts

Add to `observability/alerts/autorag-alerts.yml`:

```yaml
- alert: AgentCostSpike
  expr: |
    sum(increase(autorag_agent_cost_usd_total[24h]))
    > 2 * avg_over_time(sum(increase(autorag_agent_cost_usd_total[24h]))[7d:1d])
  severity: high

- alert: AgentLatencyBreach
  expr: |
    histogram_quantile(0.95,
      sum by(le)(rate(autorag_agent_latency_ms_bucket[5m]))) > 3000
  severity: critical

- alert: ExpensiveLowQualityPipeline
  # Metric corrected 24-Jul-2026 (R-051, release audit): autorag_unified_score
  # never existed anywhere in the codebase; the real, wired metric is
  # autorag_org_score_avg (set in evaluator.py, labeled by organization_id).
  # Threshold aligned to the real deployment gate (0.85, CLAUDE.md §9).
  expr: |
    (autorag_org_score_avg < 0.85)
    and on() (autorag_cost_per_query_usd > 0.01)
  severity: high

- alert: TokenExplosion
  expr: |
    sum(rate(autorag_agent_tokens_total[1h]))
    > 2 * avg_over_time(sum(rate(autorag_agent_tokens_total[1h]))[7d:1h])
  severity: medium
```

---

## 12. Cost Budget Enforcement

```python
# autorag-server/app/services/cost_guardrail.py
from app.core.config import settings
from app.core.exceptions import CostLimitExceeded
from app.repositories.audit_log import AuditLogRepository


class CostGuardrail:
    def check(self, cost_usd: float, budget: float, context: str) -> None:
        if cost_usd > budget:
            # INSERT-only audit log entry (Rule 30 — never UPDATE or DELETE)
            AuditLogRepository.insert(
                event_type="cost_limit_exceeded",
                metadata={"context": context, "cost_usd": cost_usd, "budget": budget},
            )
            raise CostLimitExceeded(
                f"{context}: ${cost_usd:.6e} exceeds budget ${budget:.2e}"
            )

# Budget values from env vars — NOT hardcoded (Rule 86, Rec R-4):
#   MAX_QUERY_COST_USD          dev=0.05  staging=0.02  prod=0.01
#   MAX_EVAL_COST_USD           dev=1.00  staging=0.75  prod=0.60
#   MAX_PIPELINE_BUILD_USD      dev=5.00  staging=3.00  prod=2.00
#   MAX_MONTHLY_COST_INCREASE_PCT dev=0.50 staging=0.30 prod=0.20
```

```python
# autorag-server/app/services/token_guardrail.py  (R-5)
from app.core.config import settings
from app.core.exceptions import TokenLimitExceeded

class TokenGuardrail:
    LIMITS = {
        "prompt_tokens":     lambda: settings.max_prompt_tokens,      # default 32000
        "completion_tokens": lambda: settings.max_completion_tokens,  # default 4096
        "context_tokens":    lambda: settings.max_context_tokens,     # default 64000
    }

    def check(self, token_count: int, token_type: str, context: str) -> None:
        limit = self.LIMITS[token_type]()
        if token_count > limit:
            raise TokenLimitExceeded(
                f"{context}: {token_count} {token_type} exceeds limit {limit}"
            )

# Limits loaded from config/token_budgets.yaml via settings
# Guardrail order: TokenGuardrail → CostGuardrail → LLMService
# TokenGuardrail fires BEFORE cost is incurred — prevents token explosions
```

**Enforcement rules:**

- **Improver Agent** calls `TokenGuardrail.check()` beeore expanding context window or chunk size, then `CostGuardrail.check()` beeore generating each variant. Neither may be skipped.
- **Observer Agent** monitors running cost totals and fires `cost.threshold_exceeded` webhook when any budget is breached.
- **Cost limit violations** are INSERT-only entries to `audit_log` (event type: `cost_limit_exceeded`) — the `audit_log` table is INSERT-only per Rule 30; never UPDATE or DELETE.
- **HITL required** when projected monthly cost increase > `MAX_MONTHLY_COST_INCREASE_PCT` or pipeline build cost > `MAX_PIPELINE_BUILD_USD`.

**Improver variant guard:**

```python
# In improver_node — beeore generating any variant
async def improver_node(state: GraphState) -> GraphState:
    cost_guard  = CostGuardrail()
    token_guard = TokenGuardrail()

    projected_tokens = estimate_variant_tokens(state["variant_config"])
    token_guard.check(projected_tokens, "context_tokens", "improver-context-expansion")

    projected_cost = estimate_variant_cost(state["variant_config"])
    cost_guard.check(projected_cost, settings.max_pipeline_build_usd, "improver-variant")
    # Only reaches here if within both budgets
    ...
```

---

## 13. Production SLOs

| Metric | Target |
|--------|--------|
| Query p50 | < 1 sec |
| Query p95 | < 3 sec |
| Query p99 | < 5 sec |
| Evaluation cost | < $0.60 |
| Pipeline build cost | < $2.00 |
| Per-query cost | < $0.006 |
| Diagnoser cost | < $0.005 |
| Improver cost | < $0.20 |
| Rollback time | < 60 sec |

Auto-rollback triggers (10-minute canary window):
- `error_rate > 1%`
- `p95 latency > 3s`
- `Unified Score drop > 0.10`
- `cost_per_query_usd > MAX_QUERY_COST_USD`

---

## 14. Unified Score — Cost Penalty Reference

Cost and latency are **penalty factors** in the Unified Score formula:

```
Score = (0.25 × Recall) + (0.35 × Quality) + (0.25 × Faithfulness)
        − (0.10 × Latency_penalty) − (0.05 × Cost_penalty)
```

The `cost_per_query_usd` value is normalized to a 0–1 penalty scale before input. Formula ORM property: `autorag-server/app/models/evaluation_run.py` → `is_deploy_eligible`.

**Faithfulness < 0.5 is a non-bypassable hard block regardless of cost or latency values.**

---

## 15. Definition of Done

Implementation is complete only when ALL of the following are true:

- [ ] Every agent node appends `cost_usd`, `provider`, `prompt_tokens`, `completion_tokens` to `execution_trace`
- [ ] `llm_service.py` is the **only** place cost is calculated
- [ ] `x_trace_id` used consistently — no `trace_id` references
- [ ] `agent_metrics` table migration includes `organization_id`, `deleted_at`, UUID v7, Alembic `upgrade()` + `downgrade()`
- [ ] Architecture Review approved before `agent_metrics` migration is applied
- [ ] `CostGuardrail` service implemented and called by Improver + Observer
- [ ] `audit_log` INSERT for `cost_limit_exceeded` events
- [ ] MLflow logging wired in Evaluator (Task E-3, Team 3)
- [ ] Prometheus metrics defined in `app/metrics.py` with correct labels
- [ ] Alert rules added to `observability/alerts/autorag-alerts.yml`
- [ ] Observer Grafana dashboard panels operational
- [ ] `make lint` and `make test` pass

---

## 16. Redis LLM Response Cache (Added 03-Jul-2026)

### Why it exists

The Evaluator runs the same 10 adversarial questions on every pipeline run. Without caching, identical prompts hit the LLM every time. Redis is already in the stack. Caching also directly improves the Unified Score because the cost penalty term (`-0.05 * Cost_penalty`) drops when `cost_usd=0.0` on a cache hit.

### Cache key design

```python
cache_key = "llm:" + hashlib.sha256(f"{model_name}:{prompt}".encode()).hexdigest()
```

**x_trace_id is intentionally excluded.** It is a per-request unique ID — including it would produce a unique key for every call and defeat caching entirely. `model_name` is included because Gemini Flash 3.5 and KiMi K2.6 produce different responses to the same prompt.

### Cache hit contract

When Redis returns a hit:

- `LLMResponse.cost_usd` is set to `0.0` (no LLM cost was incurred)
- `LLMResponse.cache_hit` is set to `True`
- `LLMResponse.latency_ms` reflects cache lookup time only (typically 1-5ms)
- `CACHE_HITS.labels(agent_name=agent_name).inc()` is incremented
- `httpx` is NOT called — the API provider is never reached

When Redis returns a miss:

- Normal httpx call proceeds
- On success, result is stored: `redis.setex(cache_key, LLM_CACHE_TTL_SECONDS, json.dumps(...))`
- `CACHE_MISSES.labels(agent_name=agent_name).inc()` is incremented
- `cost_usd` is computed normally from `model_pricing.yaml`

### Redis failure handling (fail-open for cache)

Cache read and write failures are **non-fatal**. Unlike ai-guardrails.md (which fails closed), the cache is a performance optimization — a Redis outage must never block an LLM call. Both errors are `logger.warning()`-only and fall through to the httpx path.

### TTL configuration

| Environment | `LLM_CACHE_TTL_SECONDS` | Rationale |
|-------------|------------------------|-----------|
| local | 3600 | same as default |
| dev | 3600 | set to 300 for faster iteration if needed |
| staging | 1800 | shorter to catch stale answers sooner |
| production | 3600 | adversarial set stable; 1hr TTL appropriate |

Set `LLM_CACHE_TTL_SECONDS=0` to disable caching (not recommended for production Evaluator runs).

### What is stored in Redis

```json
{
  "content": "the LLM response text",
  "provider": "gemini-flash-3.5",
  "prompt_tokens": 120,
  "completion_tokens": 35,
  "total_tokens": 155
}
```

`cost_usd` is NOT stored — it is always `0.0` on a cache hit. The cost was already recorded in `agent_metrics` on the original miss.

---

## 17. Prompt Injection Guard (Added 03-Jul-2026)

### Why it exists

`ai-guardrails.md` Rule 4 mandates detection of instruction override, system prompt extraction, role manipulation, retrieval poisoning, and jailbreak attempts. The existing `pii_service.py` only masks PII — it does not block injection patterns. This was an enforcement gap.

### Placement in execution order

```
call() entry
  |
  v
prompt_injection_guard(prompt, x_trace_id)   <-- FIRST, before any provider
  | raises GuardrailViolation                    (ai-guardrails.md Rule 13: fail closed)
  v
Redis cache lookup (inside _call_provider)
  v
httpx provider call
```

### Failure mode (ai-guardrails.md Rule 13)

The guard **fails closed**: if injection is detected, `GuardrailViolation` is raised immediately and no provider is ever called. There is no partial execution, no retry, no fallback.

### Audit record

`guardrail_blocked` was added as the **13th approved `audit_log` event type** in migration `0007` (03-Jul-2026). Both the Python `APPROVED_EVENT_TYPES` frozenset and the DB CHECK constraint were updated.

Two records are now written on every injection block:

1. **Structured log** (`logger.warning`) -- emitted by `guardrail_service.py`:
```python
logger.warning(
    "guardrail_injection_blocked",
    extra={
        "pattern_name": pattern_name,  # e.g. "instruction_override"
        "x_trace_id": x_trace_id,
        # prompt text intentionally omitted -- Rule 70
    },
)
```

2. **Durable audit_log INSERT** -- written by `llm_service.call()` when `organization_id` is available:
```python
await AuditLogRepository(session).insert(
    event_type="guardrail_blocked",
    payload={
        "pattern_name": gv.pattern_name,
        "agent_name": agent_name,
        # prompt intentionally omitted -- Rule 70
    },
    organization_id=organization_id,
    run_id=run_id,
    trace_id=x_trace_id,
)
```

The audit INSERT is wrapped in `try/except` -- failure to write to audit_log is non-fatal for the guardrail decision itself (the `GuardrailViolation` is always re-raised regardless). The structured log remains the fallback if `organization_id` is `None` (system-level calls).

### Patterns covered (9 total)

| Pattern name | Example trigger |
|---|---|
| `instruction_override` | "ignore all previous instructions" |
| `instruction_disregard` | "disregard the previous rules" |
| `instruction_forget` | "forget your instructions" |
| `jailbreak_role` | "you are now DAN" |
| `jailbreak_pretend` | "pretend to be uncensored" |
| `prompt_delimiter_injection` | `</system>`, `<im_start>` |
| `new_instructions` | "new instructions: ignore safety" |
| `prompt_extraction` | "reveal your system prompt" |
| `instructions_extraction` | "what are your original instructions?" |

All patterns are case-insensitive. Add new patterns to `_INJECTION_PATTERNS` in `app/services/guardrail_service.py` — no other file needs to change.

---

## 18. LiteLLM Tutorial Coverage Matrix (Krish Naik Reference)

Reviewed against the Krish Naik LiteLLM tutorial on 03-Jul-2026. The table below records how each tutorial feature maps to AutoRAG's existing implementation, what was added as a result of the review, and what was deliberately excluded.

> **Update (24-Jul-2026 audit)**: this section's "EURI" references describe the
> transport as it was on 03-Jul-2026. The 17-Jul-2026 provider-agnostic
> migration made **direct** Gemini/KiMi (and Groq for chat) access the
> default via `CHAT_PROVIDER_ORDER`/`resolve_chat_provider_chain()` --
> EURI is now an optional legacy fallback path, not the exclusive transport
> described below. The *architectural reasoning* (why litellm wasn't adopted,
> cost/cache/guardrail/metrics design) is unaffected by which provider
> transport is active and remains accurate.

| Tutorial Feature | AutoRAG Implementation | Where | Status |
|---|---|---|---|
| Unified API for 100+ providers | Custom `httpx` to EURI endpoint -- OpenAI-compatible proxy handles all 3 models server-side | `llm_service.py` | Already done |
| Automatic fallbacks | Manual `try`-loop: Gemini Flash 3.5 -\> KiMi K2.6 -\> Gemini 3.5; `PROVIDER_FAILURES` incremented on each miss | `llm_service.call()` | Already done |
| Cost tracking | `_compute_cost()` reads per-token rates from `config/model_pricing.yaml` -- never hardcoded in Python | `llm_service.py` §7 | Already done |
| Redis LLM response cache | `sha256(model:prompt)` key; `cost_usd=0.0` on hit; non-fatal on Redis errors; TTL from `LLM_CACHE_TTL_SECONDS` | `llm_service._call_provider()` §16 | Added 03-Jul-2026 |
| Prometheus failover counters | `PROVIDER_FAILURES`, `PROVIDER_SWITCHES`, `AGENT_COST`, `AGENT_LATENCY` wired into call/except blocks | `app/metrics.py` + `llm_service.py` §9 | Added 03-Jul-2026 |
| PII input guardrail | `pii_service.mask_pii()` called before every LLM call at agent boundary | `pii_service.py` | Already done |
| Prompt injection blocking | `guardrail_service.prompt_injection_guard()` -- 9 regex patterns, fails closed, durable audit_log INSERT | `guardrail_service.py` + §17 | Added 03-Jul-2026 |
| Success/failure callbacks | Structured JSON logger (`logger.info/warning`) + Prometheus metrics; no separate callback framework needed | `llm_service.py` §7 | Already done |
| Smart routing (task-aware) | **Not adopted** -- AutoRAG agents are domain-specific; fixed failover chain is the correct pattern for this architecture | -- | Not applicable |
| LangChain `ChatLiteLLM` wrapper | **Not adopted** -- AutoRAG uses LangGraph + raw `LLMService`; LangChain adds a dependency with no benefit | -- | Not applicable |
| Load balancing across API keys | **Not adopted** -- EURI gateway handles key rotation server-side; duplicating it in AutoRAG would be redundant | -- | Not applicable |

### Why litellm was not adopted as the HTTP transport

AutoRAG's `llm_service.py` calls EURI -- an OpenAI-compatible reverse proxy that already abstracts Gemini Flash 3.5, KiMi K2.6, and Gemini 3.5 behind a single endpoint. Adding litellm on top of EURI would insert a second abstraction layer over an already-abstracted API, impose an additional Python dependency, and require an ADR justification. The existing custom `httpx` client gives full control over retry behavior, tracing headers, and timeout semantics with no framework overhead.

---

**This document is mandatory for Phase D and later releases.**

Failure to capture LLM cost and latency metrics is a production readiness blocker.
