# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Improver Agent Skill

## Purpose

Build the agent that generates optimized pipeline variants based on diagnosis.

## Requirements

- **Variant Limit**: Generate exactly 3 variants per loop iteration.
- **Parameter Focus**: Adjust `chunk_size`, `top_k`, and `temperature` first.
- **Cost Guardrail**: Variant cost must not exceed the current pipeline's cost by `> 20%`.

## Anti-Patterns

- **Random Mutation**: Changing parameters without reading the `remediation_hint` from the Diagnoser.
- **Prompt Bloat**: Making prompt templates excessively long to fix a retrieval issue.

## Rule 86 Compliance

> **Mandatory before generating variants**: Call `TokenGuardrail.check_expansion_safe(current=current_tokens, increase=delta, budget_type=TokenBudgetType.CONTEXT, x_trace_id=x_trace_id)` before increasing `chunk_size` or `context_window`. Then call `CostGuardrail.check()` with estimated variant cost before dispatching. The Cost Guardrail (not the Improver node) computes `cost_usd` from `LLMService` telemetry. Violations write `cost_limit_exceeded` to `audit_log`. See `rules/86-cost-latency-monitoring.md`.
