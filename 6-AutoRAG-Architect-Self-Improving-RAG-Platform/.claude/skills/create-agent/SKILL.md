# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-agent
description: Create or modify a LangGraph agent node for AutoRAG (e.g. Query Rewriter, Diagnoser)

---

# Create Agent Skill

## Goal

Build an AutoRAG agent as a formal LangGraph node with state persistence and conditional edges.

## Steps

1. Ask for: agent purpose (one of the 9 AutoRAG agents), inputs, outputs, and sync vs async requirement.
2. Define the LangGraph node logic in `autorag-server/app/graph/nodes/`.
3. Define the explicit conditional edges that route traffic to the next agent.
4. Ensure the state object matches the global LangGraph state schema (must be PII-stripped before checkpointing).
5. If calling an LLM, implement the failover chain: Gemini Flash 3.5 &#8594; KiMi K2.6 &#8594; Gemini 3.5.
6. Add structured logging via Prometheus metrics + CloudWatch ECS native logs.
7. Add LangGraph traversal tests (mocking the LLM) to reach 90% edge coverage.

## Quality rules

- Agents are stateful through LangGraph, but stateless in memory.
- LLM upgrades must trigger a Mandatory Approval Gate.
- Never expose raw model output without passing through the Context Compressor or JSON schema validation.

## Rule 86 Compliance

> **Mandatory for any agent making LLM calls**: Route all LLM calls through `LLMService` (`app/services/llm_service.py`) — never call the provider SDK directly from a node. `LLMService` records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` into `execution_trace`. Call `TokenGuardrail.check()` before expanding context windows. `CostGuardrail.check()` fires inside `LLMService` on every call. See `rules/86-cost-latency-monitoring.md`.
