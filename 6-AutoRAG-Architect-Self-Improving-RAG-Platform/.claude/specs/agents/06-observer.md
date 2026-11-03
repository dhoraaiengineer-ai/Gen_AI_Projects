# Agent 6: Observer

**Status**: Spec | **Phase**: F-4 | **Team**: Team 10

---

## Responsibility

Continuously monitor production pipeline health: retrieval quality drift, p95 latency, LLM cost per query, and error rates. When thresholds are breached, emit the appropriate webhook event and trigger the Diagnoser agent.

---

## Input Schema

```python
class ObserverInput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    observation_window_minutes: int = 60  # rolling window to analyze
    x_trace_id: str
```

---

## Output Schema

```python
class ObserverOutput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    health_status: Literal["healthy", "degraded", "critical"]
    metrics_snapshot: MetricsSnapshot
    alerts_fired: list[str]      # list of threshold names that breached
    trigger_diagnoser: bool
    x_trace_id: str

class MetricsSnapshot(BaseModel):
    unified_score_p50: float
    unified_score_trend: float   # delta vs. previous window (negative = regression)
    latency_p95_ms: float
    error_rate_pct: float
    cost_per_query_usd: float
    recall_at_5: float
    observation_window_minutes: int
    evaluated_at: datetime
```

---

## Thresholds That Trigger Alerts

| Metric                | Threshold                          | Alert                                                       |
| --------------------- | ---------------------------------- | ----------------------------------------------------------- |
| `unified_score_trend` | Drop `> 0.10` vs. previous window  | `agent.health_degraded` webhook                             |
| `latency_p95_ms`      | `> 3000ms`                         | `agent.health_degraded` webhook                             |
| `error_rate_pct`      | `> 1%`                             | `agent.health_degraded` webhook + ECS auto-rollback trigger |
| `cost_per_query_usd`  | Exceeds configured ceiling         | `cost.threshold_exceeded` webhook                           |
| `recall_at_5`         | `< 0.80` (below production target) | `agent.health_degraded` webhook                             |

---

## Failure Modes

| Failure                        | Classification | Retry Policy                                 |
| ------------------------------ | -------------- | -------------------------------------------- |
| Prometheus metrics unavailable | Transient      | Retry once; log warning if still unavailable |
| MLflow metrics unavailable     | Transient      | Degrade gracefully — use CloudWatch only     |
| Threshold config missing       | Hard block     | Halt Observer; emit `agent.health_degraded`  |

---

## Thresholds — Additional Cost Triggers (Rule 86)

| Metric | Threshold | Alert |
|--------|-----------|-------|
| `cost_per_query_usd` | > `MAX_QUERY_COST_USD` env var | `cost.threshold_exceeded` webhook + `audit_log` INSERT |
| Monthly cost increase | > 20% vs. 7-day avg | `cost.threshold_exceeded` → HITL required |

---

## Prometheus Metrics (Rule 86)

Observer node MUST push these after each observation cycle:

```python
from app.metrics import (
    AGENT_COST, AGENT_LATENCY, AGENT_TOKENS,
    CACHE_HITS, CACHE_MISSES, CACHE_LATENCY,
    PROVIDER_FAILURES, PROVIDER_SWITCHES, PROVIDER_RATE_LIMITS, PROVIDER_TIMEOUTS,
)
```

| Metric | Type | Labels |
|--------|------|--------|
| `autorag_agent_cost_usd_total` | Counter | `agent_name`, `provider` |
| `autorag_agent_latency_ms` | Histogram | `agent_name` |
| `autorag_agent_tokens_total` | Counter | `agent_name`, `provider`, `token_type` |
| `autorag_cache_hits_total` | Counter | `agent_name` |
| `autorag_cache_misses_total` | Counter | `agent_name` |
| `autorag_cache_latency_ms` | Histogram | `agent_name` |
| `autorag_provider_failures_total` | Counter | `provider` |
| `autorag_provider_switch_total` | Counter | `from_provider`, `to_provider` |
| `autorag_provider_rate_limit_total` | Counter | `provider` |
| `autorag_provider_timeout_total` | Counter | `provider` |

---

## Model Efficiency Score

Observer dashboard MUST include the Efficiency Score panel:

```
Efficiency Score = UnifiedScore / cost_per_query_usd
```

| Model | Unified Score | Cost/Query | Efficiency |
|-------|--------------|-----------|------------|
| Gemini Flash 3.5 | 0.89 | $0.001 | 890 |
| KiMi K2.6 | 0.88 | $0.002 | 440 |
| Gemini 3.5 | 0.92 | $0.008 | 115 |

High efficiency score = best quality-per-dollar. Use this to guide Improver variant selection.

---

## Telemetry Emitted

| Event                             | When                       | Fields                                                      |
| --------------------------------- | -------------------------- | ----------------------------------------------------------- |
| `agent.health_degraded` webhook   | Any threshold breach       | `pipeline_id`, `metric`, `value`, `threshold`, `x_trace_id` |
| `cost.threshold_exceeded` webhook | Cost ceiling breach        | `pipeline_id`, `cost_usd`, `ceiling_usd`, `x_trace_id`      |
| `audit_log` INSERT                | Cost limit exceeded        | `event_type: cost_limit_exceeded`, `pipeline_id`, `x_trace_id` |
| Structured log (INFO)             | Observation cycle complete | `health_status`, `metrics_snapshot`, `x_trace_id`           |
| Prometheus metric                 | Every cycle                | `unified_score_p50`, `latency_p95`, `error_rate`            |

---

## Dependencies

- Prometheus (primary metrics source — see §Prometheus Metrics above) + Grafana dashboards (ADR-007)
- AWS CloudWatch (ECS container/infra-level logs only, not AI quality metrics)
- MLflow (score history)
- PostgreSQL `evaluations` table (score trend calculation)
- Webhook dispatcher (for outbound events)
- Diagnoser agent (triggered when `trigger_diagnoser = True`)
- `app/services/cost_guardrail.py` — `CostGuardrail` (Rule 86)
- `config/model_pricing.yaml` — provider pricing rates
- `config/token_budgets.yaml` — token limits
