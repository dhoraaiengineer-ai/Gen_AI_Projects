# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create LangGraph Workflow Skill

## Purpose

Create a production-ready, stateful LangGraph orchestrator for the AutoRAG 9-agent loop.

## Requirements

- **Stateful**: Use a typed `State` object defined in Pydantic.
- **Persistent**: Mandatory `PostgresSaver` for checkpointing between nodes.
- **Async**: Nodes must be `async def` to handle I/O-heavy LLM and Vector calls.
- **Observable**: Mandatory entry/exit logging for each node with `X-Trace-ID`.
- **Fault-Tolerant**: Built-in retry policies for transient provider failures.

## Required Components

1. `State` definition (schema-stripped for PII).
2. `Nodes` (the 9 AutoRAG agents).
3. `Edges` (conditional logic based on Unified Score thresholds).
4. `Checkpointer` (`PostgresSaver` -- PostgreSQL only; Redis is cache/job-status, not checkpoint storage).

## Anti-Patterns

- **Global Mutable State**: Never share state outside the LangGraph state object.
- **Sync Blocks**: Blocking the event loop with synchronous LLM calls.
- **Implicit Edges**: Hard-coding next-steps inside agents instead of using Graph logic.

## Rule 86 Compliance

> Every LLM-calling node in the workflow **must** route calls through `LLMService` (not the provider SDK directly). `LLMService` appends `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` to `execution_trace`. Do NOT add a separate `agent_metrics: List[AgentMetric]` field to `GraphState` without Architecture Review — use `execution_trace` entries instead. Include `TokenGuardrail` and `CostGuardrail` wiring in the workflow's node scaffolding template. See `rules/86-cost-latency-monitoring.md`.
