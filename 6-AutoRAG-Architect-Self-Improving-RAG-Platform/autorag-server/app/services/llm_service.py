"""LLM call wrapper -- Gemini Flash 3.5 -> KiMi K2.6 -> Gemini 3.5 failover chain.

Task E-15: Team 3 (Vansh / Kaushlendra Kumar Gupta)
Rule 86:
  - Every LLM call captures prompt_tokens, completion_tokens, cost_usd, latency_ms,
    provider, x_trace_id.
  - Cost calculation ONLY happens here -- never in agent nodes.
  - Provider pricing loaded from config/model_pricing.yaml at startup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import redis.asyncio as aioredis
import yaml  # type: ignore[import-untyped]

from app.core.config import (
    ProviderEndpoint,
    get_settings,
    resolve_chat_provider_chain,
    resolve_gemini,
)
from app.core.database import AsyncSessionLocal
from app.metrics import (
    AGENT_COST,
    AGENT_LATENCY,
    CACHE_HITS,
    CACHE_LATENCY,
    CACHE_MISSES,
    PROVIDER_FAILURES,
    PROVIDER_SWITCHES,
)
from app.repositories.agent_metrics_repository import AgentMetricsRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.guardrail_service import GuardrailViolation, prompt_injection_guard

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Pricing -- loaded once at import time (Rule 86: no hardcoded rates)
# ─────────────────────────────────────────────────────────────────────────────

_PRICING_PATH = (
    pathlib.Path(__file__).parent.parent.parent / "config" / "model_pricing.yaml"
)


def _load_pricing() -> dict[str, float]:
    """Load per-token USD rates from config/model_pricing.yaml."""
    try:
        with _PRICING_PATH.open() as fh:
            data: dict[str, Any] = yaml.safe_load(fh)
        return {k: float(v) for k, v in data.get("cost_per_token_usd", {}).items()}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "model_pricing_load_failed",
            extra={"path": str(_PRICING_PATH), "error": str(exc)},
        )
        return {}


_PRICING: dict[str, float] = _load_pricing()


# ─────────────────────────────────────────────────────────────────────────────
# Redis cache -- lazy singleton, reused across requests
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]


def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Lazy-init Redis client from settings.redis_url.

    Module-level singleton: one connection pool per process.
    Safe for asyncio -- aioredis manages its own event-loop-aware pool.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _redis_client


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class LLMResponse:
    """Structured result of a single LLM call -- Rule 86 compliant."""

    content: str
    provider: str          # "gemini-flash-3.5" | "kimi-k2.6" | "gemini-3.5"
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float        # computed from model_pricing.yaml, never hardcoded
    latency_ms: int
    cache_hit: bool = False  # True when response served from Redis


class LLMProviderError(Exception):
    """Raised when all three providers in the failover chain have failed."""


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _compute_cost(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost from model_pricing.yaml -- Rule 86 single cost source."""
    rate = _PRICING.get(provider, 0.0000002)  # safe default if yaml missing
    return round((prompt_tokens + completion_tokens) * rate, 8)


# ─────────────────────────────────────────────────────────────────────────────
# LLMService
# ─────────────────────────────────────────────────────────────────────────────


class LLMService:
    """Single entry point for all LLM calls in the AutoRAG platform.

    Implements the mandatory failover chain (Rule 60 + ADR 002):
        Gemini Flash 3.5  ->  KiMi K2.6  ->  Gemini 3.5

    All token counts and cost_usd are computed here and returned in LLMResponse.
    Agent nodes MUST NOT compute cost independently (Rule 86).

    Added (LiteLLM tutorial gaps):
      - Redis LLM response cache (cache_key = sha256(model:prompt); x_trace_id excluded)
      - Prometheus failover counters (PROVIDER_FAILURES, PROVIDER_SWITCHES)
      - Prompt injection guard (ai-guardrails.md Rule 4, fails closed)
    """

    async def _call_provider(
        self,
        *,
        prompt: str,
        x_trace_id: str,
        model_name: str,
        provider_label: str,
        api_key: str,
        base_url: str,
        max_tokens: int,
        agent_name: str = "unknown",
        temperature: float | None = None,
    ) -> LLMResponse:
        """Make a single HTTP call to an OpenAI-compatible chat completions endpoint.

        ``base_url`` is resolved by the caller (``call()``) via
        ``resolve_gemini()``/``resolve_kimi()`` -- this method is provider-agnostic
        and never reads settings.euri_base_url or any *_base_url field itself.

        Checks Redis cache before hitting the network. Cache key is sha256 of
        model_name + prompt -- x_trace_id is intentionally excluded so the same
        prompt/model pair hits the cache regardless of which request made it.
        """
        settings = get_settings()
        redis = _get_redis()

        # ── Redis cache lookup ─────────────────────────────────────────────
        # temperature is part of the cache key (25-Jul-2026 fix, Configurator
        # wiring) -- two requests for the same model+prompt at different
        # temperatures are NOT interchangeable and must not share a cached
        # response. Omitted (None) hashes identically to the prior key format,
        # so existing cache entries for calls that never set temperature stay
        # valid.
        cache_key = (
            "llm:"
            + hashlib.sha256(
                f"{model_name}:{temperature}:{prompt}".encode("utf-8")
                if temperature is not None
                else f"{model_name}:{prompt}".encode("utf-8")
            ).hexdigest()
        )
        cache_start = int(time.monotonic() * 1000)
        try:
            cached_raw = await redis.get(cache_key)
            cache_latency_ms = int(time.monotonic() * 1000) - cache_start
            CACHE_LATENCY.labels(agent_name=agent_name).observe(cache_latency_ms)

            if cached_raw:
                CACHE_HITS.labels(agent_name=agent_name).inc()
                data: dict[str, Any] = json.loads(cached_raw)
                logger.debug(
                    "llm_cache_hit",
                    extra={
                        "provider": provider_label,
                        "cache_latency_ms": cache_latency_ms,
                        "x_trace_id": x_trace_id,
                    },
                )
                return LLMResponse(
                    content=data["content"],
                    provider=data["provider"],
                    prompt_tokens=data["prompt_tokens"],
                    completion_tokens=data["completion_tokens"],
                    total_tokens=data["total_tokens"],
                    cost_usd=0.0,  # cache hit = no LLM cost incurred
                    latency_ms=cache_latency_ms,
                    cache_hit=True,
                )

            CACHE_MISSES.labels(agent_name=agent_name).inc()

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "llm_cache_read_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

        # ── Network call ───────────────────────────────────────────────────
        url = f"{base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Trace-ID": x_trace_id,
        }

        call_start = int(time.monotonic() * 1000)
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                # Surface the provider's own error message (e.g. "model not
                # found") instead of a generic httpx exception -- this is the
                # provider's own error envelope, never PII (Rule 85: log what
                # happened and why).
                logger.error(
                    "llm_provider_error",
                    extra={
                        "provider": provider_label,
                        "model": model_name,
                        "status": resp.status_code,
                        "body": resp.text[:500],
                        "x_trace_id": x_trace_id,
                    },
                )
                raise LLMProviderError(
                    f"{provider_label} call to model '{model_name}' failed "
                    f"({resp.status_code}): {resp.text[:500]}"
                )

        latency_ms = int(time.monotonic() * 1000) - call_start
        body: dict[str, Any] = resp.json()

        content: str = body["choices"][0]["message"]["content"]
        usage: dict[str, int] = body.get("usage", {})
        prompt_tokens: int = usage.get("prompt_tokens", 0)
        completion_tokens: int = usage.get("completion_tokens", 0)
        total_tokens: int = usage.get(
            "total_tokens", prompt_tokens + completion_tokens
        )

        # ── Cache store on successful API call ─────────────────────────────
        try:
            ttl = settings.llm_cache_ttl_seconds
            await redis.setex(
                cache_key,
                ttl,
                json.dumps(
                    {
                        "content": content,
                        "provider": provider_label,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    }
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "llm_cache_write_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

        return LLMResponse(
            content=content,
            provider=provider_label,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=_compute_cost(provider_label, prompt_tokens, completion_tokens),
            latency_ms=latency_ms,
            cache_hit=False,
        )

    async def call(
        self,
        prompt: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        agent_name: str = "unknown",
        max_tokens: int | None = None,
        temperature: float | None = None,
        preferred_provider: str | None = None,
    ) -> LLMResponse:
        """Call LLM with automatic failover. Raises LLMProviderError if all fail.

        Execution order (all three are REQUIRED before any network call):
          1. Prompt injection guard -- raises GuardrailViolation if detected
          2. Redis cache check (inside _call_provider)
          3. Provider failover loop -- Gemini Flash 3.5 -> KiMi K2.6 -> Gemini 3.5

        preferred_provider (25-Jul-2026, Configurator wiring): when set and
        present in the resolved chain, that provider is tried FIRST -- the
        other providers stay in the chain as real fallback, never removed.
        The Gemini->KiMi->Gemini failover order is a reliability contract
        (CLAUDE.md stack table), not something a pipeline config may weaken;
        this only changes which provider gets first attempt.
        """
        # ── 1. Injection guard (ai-guardrails.md Rule 4) ──────────────────
        # Must run BEFORE any provider attempt -- fail closed (Rule 13).
        # GuardrailViolation is re-raised after logging to audit_log.
        try:
            prompt_injection_guard(prompt, x_trace_id)
        except GuardrailViolation as gv:
            # guardrail_service already emits a structured warning log.
            # Also write a durable audit record -- guardrail_blocked added as the
            # 13th approved event type in migration 0007 (03-Jul-2026).
            # Prompt text is NEVER included in payload (Rule 70).
            if organization_id is not None:
                try:
                    async with AsyncSessionLocal() as session:
                        await AuditLogRepository(session).insert(
                            event_type="guardrail_blocked",
                            payload={
                                "pattern_name": gv.pattern_name,
                                "agent_name": agent_name,
                                # prompt intentionally omitted -- Rule 70
                            },
                            organization_id=organization_id,
                            run_id=run_id,
                            trace_id=x_trace_id,
                        )
                        await session.commit()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "guardrail_audit_log_failed",
                        extra={"error": str(exc), "x_trace_id": x_trace_id},
                    )
            raise

        # ── 2 + 3. Provider failover loop with cache + Prometheus counters ─
        settings = get_settings()
        tokens = max_tokens or settings.llm_max_tokens

        # Ordered chat failover chain, built from CHAT_PROVIDER_ORDER -- each
        # slot resolves independently to EURI or a direct provider endpoint
        # (resolve_chat_provider_chain(), app/core/config.py).
        providers: list[tuple[str, ProviderEndpoint]] = resolve_chat_provider_chain(settings)

        if preferred_provider is not None:
            preferred = [p for p in providers if p[0] == preferred_provider]
            rest = [p for p in providers if p[0] != preferred_provider]
            if preferred:
                providers = preferred + rest

        last_failed_provider: str | None = None
        last_error_detail: str = "no providers attempted"

        for provider_label, endpoint in providers:
            # Emit switch counter when moving to a new provider after a failure
            if last_failed_provider is not None:
                PROVIDER_SWITCHES.labels(
                    from_provider=last_failed_provider,
                    to_provider=provider_label,
                ).inc()

            try:
                response = await self._call_provider(
                    prompt=prompt,
                    x_trace_id=x_trace_id,
                    model_name=endpoint.chat_model,
                    provider_label=provider_label,
                    api_key=endpoint.api_key,
                    base_url=endpoint.base_url,
                    max_tokens=tokens,
                    agent_name=agent_name,
                    temperature=temperature,
                )

                # Prometheus success metrics (Rule 86 -- Prometheus export)
                AGENT_COST.labels(
                    agent_name=agent_name, provider=provider_label
                ).inc(response.cost_usd)
                AGENT_LATENCY.labels(agent_name=agent_name).observe(response.latency_ms)

                logger.info(
                    "llm_call_success",
                    extra={
                        "provider": provider_label,
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                        "cost_usd": response.cost_usd,
                        "latency_ms": response.latency_ms,
                        "cache_hit": response.cache_hit,
                        "x_trace_id": x_trace_id,
                    },
                )

                # Persist to agent_metrics (F-12, ADR-006, Rule 86 SS2)
                if organization_id is not None:
                    try:
                        async with AsyncSessionLocal() as session:
                            repo = AgentMetricsRepository(session)
                            await repo.insert(
                                organization_id=organization_id,
                                run_id=run_id,
                                x_trace_id=x_trace_id,
                                agent_name=agent_name,
                                provider=provider_label,
                                prompt_tokens=response.prompt_tokens,
                                completion_tokens=response.completion_tokens,
                                total_tokens=response.total_tokens,
                                cost_usd=response.cost_usd,
                                latency_ms=response.latency_ms,
                            )
                            await session.commit()
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "agent_metrics_insert_failed",
                            extra={"error": str(exc), "x_trace_id": x_trace_id},
                        )

                return response

            except Exception as exc:  # noqa: BLE001
                # Prometheus failure counter (Rule 86 -- provider_failures_total)
                PROVIDER_FAILURES.labels(provider=provider_label).inc()
                last_failed_provider = provider_label
                last_error_detail = str(exc)
                logger.warning(
                    "llm_provider_failed",
                    extra={
                        "provider": provider_label,
                        "error": last_error_detail,
                        "x_trace_id": x_trace_id,
                    },
                )

        raise LLMProviderError(
            f"All LLM providers exhausted for x_trace_id={x_trace_id}. "
            f"Last failure ({last_failed_provider}): {last_error_detail}"
        )

    async def embed(self, text: str, x_trace_id: str) -> list[float]:
        """Embed text via resolve_gemini() -- EURI by default, direct if configured.

        Used by the Late Chunking strategy (app/rag/chunking/late.py) -- a
        separate call path from embedding_service.py's EmbeddingService, but
        resolves the same way. Validates the returned dimension against
        settings.embedding_dim (FROZEN: 768).

        Returns a list of 768 floats representing the dense embedding vector.
        Raises ValueError on dimension mismatch or misconfiguration, or
        LLMProviderError with the provider's own error message on a failed
        HTTP call (e.g. "model not found") -- never a bare generic exception.
        """
        settings = get_settings()
        endpoint = resolve_gemini(settings)
        if not endpoint.api_key:
            raise ValueError("GEMINI_API_KEY not set -- cannot embed text")

        url = f"{endpoint.base_url}/embeddings"
        payload: dict[str, Any] = {
            "model": endpoint.embedding_model,
            "input": text,
            "dimensions": settings.embedding_dim,  # frozen 768-dim contract (docs/DB_SCHEMA.md)
        }
        headers = {
            "Authorization": f"Bearer {endpoint.api_key}",
            "Content-Type": "application/json",
            "X-Trace-ID": x_trace_id,
        }

        call_start = int(time.monotonic() * 1000)
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                # Surface the provider's own error message (e.g. Google's
                # "model not found") instead of a generic httpx exception --
                # never PII, this is the provider's own error envelope.
                logger.error(
                    "embed_provider_error",
                    extra={
                        "model": endpoint.embedding_model,
                        "status": resp.status_code,
                        "body": resp.text[:500],
                        "x_trace_id": x_trace_id,
                    },
                )
                raise LLMProviderError(
                    f"Embedding call to model '{endpoint.embedding_model}' failed "
                    f"({resp.status_code}): {resp.text[:500]}"
                )
        latency_ms = int(time.monotonic() * 1000) - call_start

        body: dict[str, Any] = resp.json()
        embedding: list[float] = body["data"][0]["embedding"]

        if len(embedding) != settings.embedding_dim:
            raise ValueError(
                f"Embedding dim mismatch: expected {settings.embedding_dim}, "
                f"got {len(embedding)} from {endpoint.embedding_model}"
            )

        logger.debug(
            "embed_success",
            extra={
                "model": endpoint.embedding_model,
                "dim": len(embedding),
                "latency_ms": latency_ms,
                "x_trace_id": x_trace_id,
            },
        )
        return embedding
