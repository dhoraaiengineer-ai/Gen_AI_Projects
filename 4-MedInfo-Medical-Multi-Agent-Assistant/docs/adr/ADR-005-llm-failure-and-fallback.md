# ADR-005 - LLM failure handling and fallback

**Status:** Accepted (2026-10-14)

## Context
Providers hit quotas (some gateways report a spent quota as HTTP 403), time out, or return errors. A medical
assistant must fail safely: it must never hide an emergency notice and never show an unverified answer.

## Decision
- `FallbackChatModel`: try models in chain order, skipping open circuits; retry only transient
  "unavailable" errors, with exponential backoff; a `CircuitBreaker` per model (3 failures, 30 s cool-down,
  one half-open trial).
- Error mapping: quota or rate limit (including 403/402 with quota wording) -> **429** with `Retry-After`;
  provider error -> **502**; unreachable or all circuits open -> **503**.
- **Fail open** (the rules result or fused order stands; metric and log recorded): triage LLM, scope LLM,
  re-ranker, multi-query rewriter.
- **Fail closed** (refuse): faithfulness judge on high-risk topics; any post-answer check failure.
- The emergency notice is returned even when generation fails.
- Embeddings get more retries (idempotent batches); per-user rate limits protect quotas.

## Alternatives considered
- One retry only: fragile.
- Queue and retry later: poor experience for urgent questions.
- Answer without the judge when it fails: rejected as unsafe.

## Consequences
Graceful degradation with explicit safety priorities, plus metrics and alerts on open circuits and
classifier errors. Fallback behaviour is unit-tested; **live fallback to Gemini or Groq has not been
observed yet.**
