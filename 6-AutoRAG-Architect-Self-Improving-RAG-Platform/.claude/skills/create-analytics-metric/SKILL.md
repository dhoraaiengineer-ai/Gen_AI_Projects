# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-analytics-metric
description: Add a new analytics metric, dashboard widget, or reporting endpoint

---

# Create Analytics Metric Skill

## Goal

Add a new metric, dashboard component, or analytics endpoint to the reporting system.

## Steps

1. Ask for: metric name, definition, data source, aggregation method, and visualization type.
2. Define the metric:
   - Source events/tables and aggregation logic.
   - Time granularity options (hourly, daily, weekly, monthly).
   - Dimensions for drill-down (channel, agent, category, customer tier).
3. Implement background computation:
   - Create a LangGraph background worker task or materialized view for pre-computation.
   - Store computed metrics in a dedicated analytics table.
   - Schedule periodic refresh.
4. Create the API endpoint with time-range and dimension filtering.
5. Create the frontend dashboard widget (if applicable):
   - Chart/table component with loading and empty states.
   - Real-time updates via WebSocket (if applicable).
   - RBAC-aware rendering.
6. Add tests for the aggregation logic.
7. Summarize the metric definition and access patterns.

## Quality rules

- Never compute metrics in request handlers — use background workers.
- Use materialized views or pre-computed tables for dashboard queries.
- Support time-range filtering on all analytics endpoints.
- Apply RBAC: agents see own data, supervisors see team, admins see all.
- Apply PII masking in all analytics pipelines.
- Keep metric definitions documented and versioned.
- Never expose individual customer data in aggregate views.

## Rule 86 — Cost & Token Metrics

> If adding cost or token metrics, source them from `execution_trace` entries written by `LLMService` — never re-derive from raw token counts. Prometheus metrics for cost/latency must follow the names defined in `app/metrics.py`: `autorag_agent_cost_usd_total`, `autorag_agent_latency_ms`, `autorag_agent_tokens_total`. No new metric name may duplicate these counters. See `rules/86-cost-latency-monitoring.md`.
