"""Gemini Embedding 2 batch service — D-12 (Team 5).

Produces 768-dim vectors via Gemini Embedding 2 (``text-embedding-004``) for both
document chunks (indexing) and live user queries (retrieval).

Boundaries:
- **PII masking is mandatory** — ``guardrails.input.pii_detector.mask_pii`` runs on
  every input *before* it reaches the embedding API (Rule 70 + ai-safety.md). No raw
  user or document text is ever dispatched.
- **768 is a frozen contract** (docs/DB_SCHEMA.md). A vector of any other length is
  rejected, never silently stored. The dimension lives in ``EMBEDDING_DIM`` — never an
  inline magic number.
- **No cost calculation here.** Rule 86 §2: ``cost_usd`` is computed *only* in
  ``app/services/llm_service.py``. This service deals in vectors, not spend.

``task_type``:
- ``retrieval_document`` — embedding chunks for indexing (``embed_batch``)
- ``retrieval_query``    — embedding a live user query   (``embed_query``)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.core.config import resolve_gemini, settings
from app.core.exceptions import LLMProviderError
from app.guardrails.input.pii_detector import mask_pii
from app.metrics import CACHE_HITS, CACHE_LATENCY, CACHE_MISSES

logger = logging.getLogger(__name__)

# Frozen 768-dim contract (docs/DB_SCHEMA.md). Use the constant — never hardcode 768.
EMBEDDING_DIM: int = settings.embedding_dim

_TASK_DOCUMENT = "retrieval_document"
_TASK_QUERY = "retrieval_query"

# ─────────────────────────────────────────────────────────────────────────────
# Redis cache -- lazy singleton, mirrors llm_service.py's _get_redis() pattern.
# 19-Jul-2026: embed_query() had NO caching at all -- unlike chat calls
# (llm_service.py), every retrieval, including repeated identical test queries,
# made a fresh embedding API call. Live-confirmed same evening: repeatedly
# re-running the same query while diagnosing an unrelated evaluator bug burned
# real quota on an EURI key that then hit its daily token cap ("Daily token
# limit of 100414 reached ... add funds to your wallet"). Caching the query
# embedding (keyed on masked text + model, TTL-bound) removes that waste for
# the common "same question asked again" case without touching embed_batch()
# (ingestion-time chunk embeddings are one-time by nature and not worth caching).
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]


def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Lazy-init Redis client from settings.redis_url (module-level singleton)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client

# 17-Jul-2026: EURI's embeddings endpoint has been directly observed to 500
# intermittently (confirmed transient, not a code/config bug -- see
# docs/case-study-large-document-ingestion-16jul2026.md). With
# EMBEDDING_BATCH_SIZE=100, a 200-chunk document makes 2+ separate batch
# calls; one transient 500 in any single batch previously killed the entire
# ingestion with zero retry, even after earlier batches had already
# succeeded and been persisted. Bounded retry with backoff is an HTTP-client
# resilience concern (this is a single network call, not orchestration
# logic) -- not the "inline retry loop inside a graph node" pattern
# rules/graph-state-governance.md Rule 9 forbids; retries here don't cross
# node boundaries or touch GraphState.
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 1.0

# 19-Jul-2026: embed_batch() fired every batch immediately after the previous one
# returned -- zero pacing. Live-confirmed same day: a 115-page real document
# (cil-annual-report-2025.pdf) produced enough chunks to burst multiple batch
# calls within a few seconds, tripping Google AI Studio's free-tier per-minute
# RPM limit even after the 429-retry fix above (retries exhausted, all within
# the same throttled window -- see docs/case-study-large-document-ingestion-16jul2026.md
# and MEMORY.md). This is a *burst* problem, not a daily-quota problem: a single
# isolated embed_query() call succeeds immediately after a batch failure. Spacing
# batches out is the free, no-billing-change fix; skipped after the final batch
# so single-batch documents (the common case) see zero added latency.
_INTER_BATCH_DELAY_SECONDS = 2.0


class EmbeddingService:
    """Batch + single-query embedding over Gemini Embedding 2.

    Every input is PII-masked before dispatch; every returned vector is validated
    against the frozen ``EMBEDDING_DIM`` (768) contract.
    """

    def __init__(self, batch_size: int | None = None) -> None:
        self._batch_size = (
            settings.embedding_batch_size if batch_size is None else batch_size
        )
        if self._batch_size < 1:
            raise ValueError(f"embedding batch_size must be >= 1, got {self._batch_size}")

    async def embed_batch(
        self, texts: list[str], x_trace_id: str = ""
    ) -> list[list[float]]:
        """Embed document chunks — one 768-dim vector per input text.

        Inputs are PII-masked, then dispatched in batches of ``EMBEDDING_BATCH_SIZE``
        with ``task_type="retrieval_document"``.
        """
        if not texts:
            return []

        masked = [await mask_pii(text, trace_id=x_trace_id) for text in texts]

        # 17-Jul-2026 fix: a chunk that is entirely PII (e.g. a line that is
        # just an email/phone/etc.) can come out of masking empty or
        # whitespace-only even when the pre-mask chunk_text was non-empty --
        # live-confirmed via response-body logging that EURI's embeddings
        # endpoint (which wraps Google's Gemini embedding API) rejects an
        # empty input with "EmbedContentRequest.content contains an empty
        # Part", which EURI's own gateway then mangles into a bare 500
        # instead of passing through the real 400. A placeholder keeps this
        # list's length/order aligned 1:1 with `texts` -- callers (Builder)
        # zip() the returned vectors back against their original chunk list
        # positionally, so dropping an entry here would silently misalign
        # every embedding after it.
        masked = [text if text.strip() else "[no content]" for text in masked]

        vectors: list[list[float]] = []
        batch_starts = list(range(0, len(masked), self._batch_size))
        for i, start in enumerate(batch_starts):
            batch = masked[start : start + self._batch_size]
            vectors.extend(
                await self._embed(batch, task_type=_TASK_DOCUMENT, x_trace_id=x_trace_id)
            )
            # Pace multi-batch documents so consecutive calls don't burst past the
            # embedding provider's per-minute RPM limit -- skipped after the last
            # batch (including the common single-batch case, which never sleeps).
            if i < len(batch_starts) - 1:
                await asyncio.sleep(_INTER_BATCH_DELAY_SECONDS)

        logger.info(
            "Embedding batch complete",
            extra={
                "x_trace_id": x_trace_id,
                "count": len(vectors),
                "dim": EMBEDDING_DIM,
                "batch_size": self._batch_size,
            },
        )
        return vectors

    async def embed_query(self, text: str, x_trace_id: str = "") -> list[float]:
        """Embed a single user query — one 768-dim vector.

        Input is PII-masked, then dispatched with ``task_type="retrieval_query"``.
        Checks the Redis cache first (keyed on masked text) so repeated identical
        queries -- common during testing/demos -- don't burn embedding quota.
        """
        masked = await mask_pii(text, trace_id=x_trace_id)

        redis = _get_redis()
        cache_key = "embed_query:" + hashlib.sha256(masked.encode("utf-8")).hexdigest()
        cache_start = int(time.monotonic() * 1000)
        try:
            cached_raw = await redis.get(cache_key)
            cache_latency_ms = int(time.monotonic() * 1000) - cache_start
            CACHE_LATENCY.labels(agent_name="embedding").observe(cache_latency_ms)
            if cached_raw:
                CACHE_HITS.labels(agent_name="embedding").inc()
                cached_vector: list[float] = json.loads(cached_raw)
                logger.debug(
                    "embedding_cache_hit",
                    extra={"x_trace_id": x_trace_id, "cache_latency_ms": cache_latency_ms},
                )
                return cached_vector
            CACHE_MISSES.labels(agent_name="embedding").inc()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "embedding_cache_read_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

        vectors = await self._embed([masked], task_type=_TASK_QUERY, x_trace_id=x_trace_id)
        vector = vectors[0]

        try:
            await redis.setex(cache_key, settings.llm_cache_ttl_seconds, json.dumps(vector))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "embedding_cache_write_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

        return vector

    # ── internal ────────────────────────────────────────────────────────────────

    async def _embed(
        self, contents: list[str], task_type: str, x_trace_id: str
    ) -> list[list[float]]:
        """One OpenAI-compatible ``/embeddings`` call for already-masked texts.

        Resolves the same way as ``llm_service.py``'s chat completions --
        ``resolve_gemini()`` -- so this routes through EURI by default, or
        directly to a real provider if ``GEMINI_BASE_URL`` is configured.
        The deprecated ``google.generativeai`` SDK is never used here: calling
        Google's real API directly with an EURI-formatted key rejects it with
        "API key not valid," which is exactly why this is resolved per-request
        rather than hardcoded to one gateway.
        """
        endpoint = resolve_gemini(settings)
        url = f"{endpoint.base_url}/embeddings"
        payload: dict[str, Any] = {
            "model": endpoint.embedding_model,
            "input": contents,
            "dimensions": EMBEDDING_DIM,  # frozen 768-dim contract (docs/DB_SCHEMA.md)
        }
        headers = {
            "Authorization": f"Bearer {endpoint.api_key}",
            "Content-Type": "application/json",
            "X-Trace-ID": x_trace_id,
        }

        body: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                start = time.monotonic()
                async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code >= 400:
                        # Surface the provider's actual error body (never PII --
                        # this is EURI's own error envelope, e.g. quota/auth
                        # messages) so real causes aren't hidden behind a bare
                        # status code. Rule 85: log what happened and why.
                        logger.error(
                            "Embedding provider error status=%s batch_len=%s body=%s",
                            resp.status_code,
                            len(contents),
                            resp.text[:500],
                            extra={"x_trace_id": x_trace_id},
                        )
                    resp.raise_for_status()
                latency_ms = int((time.monotonic() - start) * 1000)
                body = resp.json()
                break
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                # 429 (rate limit) is transient and must back off + retry -- live-confirmed
                # 17-Jul-2026: a 113-page/605K-char document hit Google AI Studio's free-tier
                # embedding rate limit mid-ingestion and previously failed the entire document
                # outright on the first 429, wasting the batches that had already succeeded.
                # Other 4xx (400/401/403 -- bad request/auth/payload) genuinely won't be fixed
                # by retrying, so those still fail fast.
                if exc.response.status_code != 429 and exc.response.status_code < 500:
                    logger.error(
                        "Embedding call failed (non-retryable)",
                        extra={"x_trace_id": x_trace_id, "error": str(exc), "status": exc.response.status_code},
                    )
                    raise LLMProviderError(
                        f"{endpoint.embedding_model} embedding failed: {exc}", x_trace_id=x_trace_id
                    ) from exc
                logger.warning(
                    "Embedding call failed (transient, retrying)",
                    extra={
                        "x_trace_id": x_trace_id,
                        "error": str(exc),
                        "status": exc.response.status_code,
                        "attempt": attempt + 1,
                        "max_retries": _MAX_RETRIES,
                    },
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning(
                    "Embedding call failed (network error, retrying)",
                    extra={
                        "x_trace_id": x_trace_id,
                        "error": str(exc),
                        "attempt": attempt + 1,
                        "max_retries": _MAX_RETRIES,
                    },
                )
            except Exception as exc:
                # Unexpected error shape (e.g. malformed JSON) -- not retryable.
                logger.error(
                    "Embedding call failed (unexpected)",
                    extra={"x_trace_id": x_trace_id, "error": str(exc)},
                )
                raise LLMProviderError(
                    f"{endpoint.embedding_model} embedding failed: {exc}", x_trace_id=x_trace_id
                ) from exc

            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)

        if body is None:
            logger.error(
                "Embedding call failed (exhausted retries)",
                extra={"x_trace_id": x_trace_id, "error": str(last_exc), "attempts": _MAX_RETRIES + 1},
            )
            raise LLMProviderError(
                f"{endpoint.embedding_model} embedding failed after {_MAX_RETRIES + 1} attempts: {last_exc}",
                x_trace_id=x_trace_id,
            ) from last_exc

        # OpenAI-compatible shape: {"data": [{"embedding": [...], "index": 0}, ...]}
        # index order is not guaranteed to match input order -- sort defensively.
        items = sorted(body["data"], key=lambda d: d.get("index", 0))
        vectors: list[list[float]] = [item["embedding"] for item in items]

        for vector in vectors:
            if len(vector) != EMBEDDING_DIM:
                raise LLMProviderError(
                    f"Embedding dim mismatch: got {len(vector)}, "
                    f"expected {EMBEDDING_DIM} (frozen contract — docs/DB_SCHEMA.md)",
                    x_trace_id=x_trace_id,
                )

        logger.debug(
            "Embedding call ok",
            extra={
                "x_trace_id": x_trace_id,
                "task_type": task_type,
                "count": len(vectors),
                "latency_ms": latency_ms,
            },
        )
        return vectors
