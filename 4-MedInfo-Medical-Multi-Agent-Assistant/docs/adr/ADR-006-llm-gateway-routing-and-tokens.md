# ADR-006 - LLM gateway: model routing, token limits and caching

**Status:** Accepted (2026-10-15)

## Context
Model calls were made directly by each component (triage, scope, re-ranker, rewriter, answer, judge), each
with its own hard-coded `max_tokens`. That gave no single place to route cheap classification work to a
cheaper model, no minimum output budget (reasoning models return empty text when `max_tokens` is tiny), no
input budget for the answer prompt, no token accounting, and no cache for repeated query embeddings.

## Decision
- **One gateway** (`backend/app/rag/gateway.py`): every chat-model call goes through
  `gateway.for_task(task)`, which keeps the existing `ChatModel` interface, so components did not change.
- **Routing table** (`backend/app/rag/llm_gateway.yaml`): each task names a route. `quality` is
  `LLM_ANSWER_CHAIN` (answer, faithfulness judge, evaluation judge). `fast` is `LLM_FAST_CHAIN` if set,
  otherwise the answer chain (triage, scope, rewrite, re-rank). Each route is the existing fallback chain
  with circuit breakers (ADR-005).
- **Token limits per task**: the requested output budget is clamped to `[min_output_tokens,
  max_output_tokens]`. A prompt whose estimated size exceeds `max_input_tokens` is not sent. For the answer,
  the lowest-ranked passages are dropped until the prompt fits, and the graph returns the kept list, so the
  verifier checks exactly what the model saw.
- **Estimates offline**: budgeting uses characters / 4 (no tokenizer download). Real usage reported by the
  provider is recorded per task, model and direction (`medinfo_llm_tokens_total`).
- **Caching**: the answer cache and the LLM prompt cache stay as they are. A new query-embedding cache keys on
  a hash of (model, dimensions, text) and stores vectors only (`EMBEDDING_CACHE_TTL_SECONDS`).
- **Safety first**: an over-budget call behaves like a failed model call. Triage and scope fall back to the
  local rules; the judge fails closed.

## Alternatives considered
- External gateway product (LiteLLM proxy, Portkey, a cloud AI gateway): adds a service to run and secure, and
  sends prompts through another hop. The in-process gateway covers routing, limits and accounting. An
  external gateway can still sit behind the provider base URLs later. EURI is itself an OpenAI-compatible
  gateway.
- Exact tokenizer (tiktoken): accurate, but downloads encodings at runtime and differs per provider. The
  estimate is conservative and provider-neutral.
- Complexity-based routing (choose a model per question): harder to test and to keep safe. Routing by task
  is deterministic.

## Consequences
- Implemented and tested offline: `tests/test_gateway.py` and `tests/safety/test_gateway_safety.py`.
- Not yet verified live: real token usage numbers and a separate `LLM_FAST_CHAIN` have not been run against
  providers. No cost savings are claimed until a live run measures them.
- Moving the safety judge to the `fast` route requires a live evaluation showing it is as strict.
