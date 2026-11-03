# ADR-002: Gemini Flash 3.5 as Primary LLM with KiMi K2.6 Fallback

**Status**: Accepted | **Date**: 05-Jul-2026
**Deciders**: Mahesh Kumar

## Decision

Replace the previous multi-vendor LLM setup (OpenAI / Claude / Gemini Flash 3.5) with a single primary-plus-fallback chain:

```
Gemini Flash 3.5  →  KiMi K2.6  →  Gemini 3.5
   (primary)           (fallback)     (last resort)
```

All LLM calls in the 9-agent loop use this chain exclusively. Model selection is centralized in `app/services/llm_service.py`.

## Rationale

- **Cost**: Gemini Flash 3.5 is significantly cheaper per token than GPT-4o and Claude-3.x for RAG-style retrieval-augmented generation tasks
- **Context window**: 1M-token context window supports long document ingestion and multi-chunk retrieval without truncation
- **Embedding alignment**: Gemini Embedding 2 (768-dim) pairs natively with Gemini Flash generation — no cross-vendor serialization overhead
- **EURI API compatibility**: EURI API provides budget-controlled access to both Gemini and KiMi endpoints under a single API key
- **Vendor consolidation**: Eliminates three separate LLM vendor integrations (OpenAI, Anthropic, Gemini Flash 3.5 local); reduces operational surface
- **Determinism**: Single provider pair with known failover semantics is more predictable than dynamic multi-vendor routing

## Failover Logic

| Step | Provider | Trigger to Fallback |
|------|----------|---------------------|
| 1 | Gemini Flash 3.5 | `429 RateLimitError` or `503 ServiceUnavailable` |
| 2 | KiMi K2.6 | `429 RateLimitError` or `503 ServiceUnavailable` |
| 3 | Gemini 3.5 | Last resort — no further fallback |

`llm_provider_used` field in `GraphState` reflects the active provider for each run.

## Embedding Decision

| Removed | Replaced By | Dimension |
|---------|-------------|-----------|
| OpenAI text-embedding-3-large | Gemini Embedding 2 | 1536-dim → **768-dim** |

Embedding dimension 768 is frozen in the v1.0 GraphState contract. Changing it requires a full re-index of all Supabase Vector tables.

## Consequences

- All new LLM calls must go through `app/services/llm_service.py` — no direct SDK calls in agent nodes
- Cost calculation (`cost_usd`) is computed only in `llm_service.py` — never in agent nodes (Rule 86)
- Gemini Embedding 2 (768-dim) is the production embedding standard — cannot be changed without Architecture Review
- Local inference (Gemini Flash 3.5) is removed — `local` environment uses Gemini API with a real key
- Model upgrades are a **Mandatory Gate** change — requires Architecture Review + evaluator regression pass

## See Also

- [rules/86-cost-latency-monitoring.md](../rules/86-cost-latency-monitoring.md) — LLM cost + token tracking; CostGuardrail + TokenGuardrail enforcement
- [specs/stack.md](../specs/stack.md) — full technology stack
- [specs/agents/](../specs/agents/) — per-agent LLM usage patterns
- [docs/AGENT_COST_AND_LATENCY_GUIDE.md](../docs/AGENT_COST_AND_LATENCY_GUIDE.md) — cost guardrail implementation
- [adr/007-observability-stack.md](007-observability-stack.md) — why Langfuse was rejected; LLM observability covered by execution_trace + MLflow
