# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Query Rewriter Skill

## Purpose

Build the Query Rewriter node to optimize user queries before they hit the embedding stage.

## Requirements

- **Multi-Form**: Generate 3 forms of the query: (1) Literal, (2) Semantic Intent, (3) Keyword-heavy.
- **Latency**: Must execute in `< 100ms` using Gemini Flash 3.5 (matches `docs/AGENT_COST_AND_LATENCY_GUIDE.md`'s Agent 2 target).
- **Context Awareness**: Use the last 2 turns of conversation history if available.

## Anti-Patterns

- **Over-Writing**: Changing the core meaning of a user's specific query.
- **Using Sonnet**: Using expensive models for simple rewriting (violates Cost SLO).

## Rule 86 Compliance

> Route all Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 calls through `LLMService`. Token usage (`prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`) is recorded automatically into `execution_trace`. The node must not compute cost independently. Provider pricing is loaded from `config/model_pricing.yaml`. See `rules/86-cost-latency-monitoring.md`.
