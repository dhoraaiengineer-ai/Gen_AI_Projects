# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Debug RAG Failures Skill

## Purpose

Scaffold the Diagnoser Agent's logic for classifying pipeline failures.

## The 6-Part Taxonomy (F-06 Quality Drift added via G-6, 10-Jul-2026)

1. **Retrieval Miss**: No relevant chunks found in the top-K.
2. **Context Overflow**: Relevant chunks truncated by context window.
3. **Hallucination**: Generated answer contradicts retrieved chunks.
4. **Incompleteness**: Answer is factually correct but missing requested details.
5. **Latency Spike**: p95 > 3 seconds.
6. **Quality Drift**: Sustained Unified Score decline across a 5-run rolling window.

## Diagnosis Steps

1. Parse `judge_reasoning` from the Evaluator Agent.
2. Compare query embedding vs retrieved chunk similarity.
3. Calculate token density of relevant vs irrelevant text in context.
4. Cross-reference `audit_log` for provider timeouts.

## Anti-Patterns

- **Generic Errors**: Classifying all quality drops as "Low Quality".
- **Silent Failures**: Missing a latency spike because total score is high.

## Rule 86 — Cost & Latency in Failure Diagnosis

> When diagnosing `Latency Spike` or cost regressions, check:
> 1. `execution_trace` entries for `latency_ms` and `cost_usd` per node
> 2. Prometheus metrics: `autorag_agent_latency_ms` and `autorag_agent_cost_usd_total`
> 3. `audit_log` for `cost_limit_exceeded` events (written by `CostGuardrail`)
> 4. `agent_metrics` table in PostgreSQL (live since migration 0006, 03-Jul-2026 -- ADR-006 approved; per-node cost/latency detail, not just the `evaluation_runs.cost_usd` aggregate)
> High cost is a 5% penalty in Unified Score (`-0.05×Cost`) — cost spikes can push score below the 0.85 deployment gate. See `rules/86-cost-latency-monitoring.md`.
