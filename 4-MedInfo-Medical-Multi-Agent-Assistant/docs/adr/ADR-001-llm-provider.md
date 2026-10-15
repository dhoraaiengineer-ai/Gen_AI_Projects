# ADR-001 - LLM provider strategy

**Status:** Accepted (2026-10-14)

## Context
The assistant needs chat models for classifiers, re-ranking, answers and judging, plus embeddings. Keys are
available for EURI, Google Gemini and Groq. Free tiers have small quotas, and providers fail independently.

## Decision
- Use **OpenAI-compatible endpoints only** (via `langchain-openai`), behind the `ChatModel` interface.
- **Answer chain:** `euri:gpt-4.1-mini` -> `gemini:<model>` -> `groq:openai/gpt-oss-120b`
  (`LLM_ANSWER_CHAIN`), with a circuit breaker per model (see ADR-005).
- **Agent chain** excludes Gemini (see ADR-002).
- **Temperatures:** answers 0.1-0.3 (enforced in settings); classifiers, re-ranker and judges 0.
- **Embeddings:** one provider per collection: EURI `text-embedding-3-small`, 1536 dimensions. The
  collection name encodes provider, model and dimensions, so switching models forces a new collection
  and a re-ingest (vectors are never mixed).
- Reasoning models (gpt-oss, Gemini 3) run with `reasoning_effort="low"` so thinking does not consume
  the output budget.

## Alternatives considered
- Single provider: simpler, but one outage or spent quota takes the service down.
- Native SDK per provider: more code, harder to fake in tests.
- Local models: no GPU available; quality and latency unknown.

## Consequences
Provider-specific code is confined to `backend/app/rag/providers.py`. Prompts must work across models.
**Verified live:** EURI chat and embeddings. **Not yet observed live:** fallback to Gemini or Groq.
