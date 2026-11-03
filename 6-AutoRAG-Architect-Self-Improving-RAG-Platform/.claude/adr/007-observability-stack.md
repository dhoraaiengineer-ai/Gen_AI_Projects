# ADR-007: Observability Stack — Tool Selection and Rejections

**Status**: Accepted — Mahesh Kumar, 09-Jul-2026 | **Date**: 09-Jul-2026
**Proposer**: Mahesh Kumar (Architecture Review Session)
**Deciders**: Mahesh Kumar
**Affects**: Monitoring & Observability layer — `observability/`, `autorag-server/app/metrics.py`, Rule 85, Rule 86

---

## Decision

AutoRAG v3.0 retains its current observability stack unchanged:

```
Prometheus + Grafana        ← metrics + dashboards
AWS CloudWatch              ← ECS container logs (native driver)
MLflow                      ← experiment tracking + variant lineage
RAGAS                       ← RAG evaluation (faithfulness, recall, precision)
X-Trace-ID propagation      ← distributed tracing (lightweight, PII-safe)
structlog (JSON)            ← structured logging with trace correlation
```

Five proposed additions are **rejected** for Phase 1.
One addition (OpenTelemetry + Tempo) is **deferred to Phase 2**.
Four v4 enhancements are **approved for future implementation** without ADR gate.

---

## Context / Problem

During the v3.0 observability review (09-Jul-2026), the stack was rated **9.5/10** against
enterprise AI/RAG production standards. A parallel review proposed expanding the stack with:

- **Loki** (log aggregation)
- **Sentry** (error tracking)
- **Langfuse** (LLM observability)
- **TruLens or Arize Phoenix** (RAG evaluation)
- **OpenTelemetry + Grafana Tempo** (distributed tracing)

Each was evaluated against AutoRAG's existing capabilities, PII safety requirements, and
the no-framework-sprawl rule (CLAUDE.md §6: "Avoid framework sprawl — no new frameworks
without ADR justification; prefer existing stack").

---

## Alternatives Considered and Rejected

### Loki (Log Aggregation) — Rejected

| Criterion | Assessment |
|-----------|-----------|
| Capability gap | None. AWS CloudWatch already stores, queries, and alerts on ECS container logs via the native `awslogs` log driver — zero configuration required. |
| Operational cost | Loki requires a log shipper sidecar (Promtail or Fluentbit) in every ECS task definition, plus a Loki server deployment and a second Grafana datasource. |
| Duplication | JSON structured logs from `structlog` are already being written to CloudWatch. Shipping them to Loki creates two stores of the same data with no additional query capability. |

**Decision: Do not add. CloudWatch covers the use case with zero overhead.**

---

### Sentry (Error Tracking) — Rejected

| Criterion | Assessment |
|-----------|-----------|
| Prior decision | Sentry was **explicitly removed in v3.0 audit** (commit `1e66809`). Reason: PII risk — LangGraph state snapshots captured in Sentry error traces can contain customer document content and user queries. Custom scrubbing rules proved fragile. |
| Capability gap | FastAPI global exception handler in `app/main.py` catches all unhandled exceptions. Structured JSON logs with `x_trace_id` provide "who broke what" tracing. Prometheus `autorag_*_total` counters + CloudWatch Alarms replace Sentry alerting. |
| PII compliance | Sentry SDKs capture stack locals and request bodies by default. Disabling all capture while keeping useful diagnostics requires per-team configuration discipline that creates a recurring audit burden. |

**Decision: Do not reintroduce. Sentry was removed for documented PII reasons; the capability is already covered.**

---

### Langfuse (LLM Observability) — Rejected

| Criterion | Assessment |
|-----------|-----------|
| Capability overlap | AutoRAG has a purpose-built equivalent: every LLM call records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `provider`, and `x_trace_id` in `execution_trace` (Rule 86). MLflow captures experiment lineage per variant. |
| Specific Langfuse features vs AutoRAG equivalents | |
| → Token + cost per LLM call | `execution_trace` entries in GraphState → `agent_metrics` table (ADR-006) |
| → LLM call latency | `latency_ms` in `execution_trace`; `autorag_agent_latency_ms` Prometheus histogram |
| → Prompt version tracking | Jinja2 templates with mandatory `vX.Y.Z` tags (Rule 50 §3) |
| → Experiment comparison | MLflow runs — one per Improver variant |
| → Distributed trace | `x_trace_id` propagation across all 9 nodes + API + audit log |
| Conflict risk | Adding Langfuse creates two parallel data flows for the same LLM call: `execution_trace` (required by Rule 86) AND Langfuse SDK. These will diverge. The `execution_trace` is a frozen contract; Langfuse would be a second opinion with no authority. |
| When Langfuse becomes appropriate | If a chat interface is added where human users generate conversational queries (per-user session history, human feedback annotation). Not applicable to AutoRAG's autonomous pipeline loop. |

**Decision: Do not add for Phase 1. Revisit if a user-facing chat interface is built.**

---

### TruLens / Arize Phoenix (RAG Evaluation) — Rejected

| Criterion | Assessment |
|-----------|-----------|
| Capability overlap | RAGAS already provides Faithfulness, Context Precision, Context Recall, Answer Relevancy, and Groundedness. The Evaluator Agent's 3-layer stack (Unified Score + RAGAS + Adversarial Q&A) covers the same signal space. |
| Arize Phoenix drift detection | The drift detection capability (embedding drift, retrieval drift, hallucination trend) is valuable but does not require the full Arize platform. It is planned as Gap 4 in the v4 roadmap using existing `evaluation_runs` data — no new external dependency needed. |
| Deployment complexity | TruLens and Arize Phoenix both require a server component and SDK instrumentation that wraps LLM calls. This conflicts with Rule 86's requirement that all LLM call tracking is centralized in `llm_service.py` — a second wrapping layer would create duplicate cost records. |

**Decision: Do not add. RAGAS is the approved evaluation layer. Drift detection is a v4 internal enhancement.**

---

### OpenTelemetry + Grafana Tempo (Distributed Tracing) — Deferred to Phase 2

| Criterion | Assessment |
|-----------|-----------|
| Is it additive? | Yes — OTel provides nested spans and flame graphs that X-Trace-ID cannot. This is the only proposed tool with a genuine capability gap. |
| Why defer? | OTel requires instrumenting all four ECS services (FastAPI, LangGraph workers, Redis client, Supabase client) plus deploying an OTel Collector sidecar in every task. Estimated: 2-engineer weeks. X-Trace-ID covers 90% of production debugging needs today. |
| Phase 1 verdict | Out of scope. The investment is disproportionate to the current debugging need. |
| Phase 2 trigger | When cross-service latency attribution (which ECS task contributed how many ms) becomes a production bottleneck — likely once traffic scales beyond 10 concurrent pipeline runs. |

**Decision: Defer. Approved for Phase 2. OTel + Tempo is ADR-eligible when Phase 2 begins.**

---

## Approved v4 Enhancements (No ADR Gate Required)

These additions extend the current stack without replacing any component. No frozen-contract changes.

| Enhancement | Priority | Effort | Notes |
|-------------|----------|--------|-------|
| Continuous Profiling (Pyroscope) | High | ~3 days | `pyroscope-io` SDK; tag by `agent_name` + `x_trace_id`; adds profiling panel to Grafana |
| Business Metrics | Medium | ~2 days | New Prometheus counters: `autorag_queries_total{org, pipeline}`, `autorag_cost_per_tenant_usd_total`, `autorag_hitl_pending_total`; no frozen-contract change |
| AI Ops Dashboard | Medium | ~2 days | New Grafana JSON: unified executive KPI view (Health Score, Unified Score, Faithfulness, Recall, Cost, HITL queue, Burn Rate, Top Failure Types) |
| AI Drift Detection | Lower | ~5 days | Rolling `evaluation_runs` comparison for embedding drift + hallucination trend; feeds Diagnoser. Needs ADR if `GraphState` field is added. |

Full details: [docs/observability-v4-roadmap.md](../docs/observability-v4-roadmap.md)

---

## Current Stack Rating (Post-Review)

| Area               | Rating |
| ------------------ | -----: |
| Metrics            |  10/10 |
| Logging            |  10/10 |
| Tracing            |   9/10 |
| MLflow             |  10/10 |
| Alerting           |  10/10 |
| SLOs               |  10/10 |
| Dashboards         |  10/10 |
| Profiling          |   6/10 |
| Business Metrics   |   8/10 |
| AI Drift Detection |   8/10 |
| **Overall**        | **9.5/10** |

---

## Consequences

- **No new packages or vendor accounts** are introduced in Phase 1.
- **Sentry is permanently rejected** for AutoRAG — future engineers should reference this ADR before reopening the discussion.
- **Langfuse is not the right tool** for AutoRAG's pipeline-loop observability model; it is appropriate only for human-facing chat products.
- **OpenTelemetry is the correct long-term tracing solution** but the migration cost defers it to Phase 2.
- **v4 roadmap items** (`observability-v4-roadmap.md`) are pre-approved to proceed without a new ADR unless they touch a frozen contract (GraphState, DB schema, API spec).

---

## See Also

- [rules/85-error-observability.md](../rules/85-error-observability.md) — structured logs, tracing, health checks
- [rules/86-cost-latency-monitoring.md](../rules/86-cost-latency-monitoring.md) — token capture, Prometheus export, MLflow telemetry
- [docs/observability-v4-roadmap.md](../docs/observability-v4-roadmap.md) — v4 enhancements: profiling, business metrics, AI Ops dashboard, drift detection
- [observability/alerts/autorag-alerts.yml](../../observability/alerts/autorag-alerts.yml) — 12 alert rules (3 groups: SLO, cost/latency, provider failover)
- [observability/slo/slo-definitions.md](../../observability/slo/slo-definitions.md) — 7 SLOs with error budget and burn rate thresholds
- [adr/006-agent-metrics-table.md](006-agent-metrics-table.md) — `agent_metrics` durable store (Rule 86 backing table)
