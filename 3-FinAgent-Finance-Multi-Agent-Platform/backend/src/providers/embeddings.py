"""Embedding providers (bi-encoder) with retries, circuit breaker and a dimension check.

Embeddings retry up to 4 times with exponential backoff (they are idempotent and usually run in
batches during ingestion). Every vector must have the configured dimensions, because the
pgvector column is fixed at ``vector(1536)`` and embeddings from different models can't be mixed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from src.config.settings import Settings
from src.core.errors import AppError, ProviderError, ProviderUnavailable, map_provider_exception
from src.core.metrics import EMBEDDING_LATENCY, EMBEDDING_REQUESTS
from src.core.retry import retry_async, retry_sync
from src.providers.llm import BREAKERS
from src.rag.embeddings import HashEmbeddings

logger = logging.getLogger(__name__)

EMBEDDING_ATTEMPTS = 4


class ResilientOpenAIEmbeddings(OpenAIEmbeddings):
    resilience_key: str = ""
    provider_name: str = "openai"
    expected_dimensions: int = 1536

    def _check(self, vectors: list[list[float]]) -> list[list[float]]:
        bad = {len(v) for v in vectors if len(v) != self.expected_dimensions}
        if bad:
            raise ProviderError(
                "embedding dimension mismatch",
                details={
                    "model": self.resilience_key,
                    "expected": self.expected_dimensions,
                    "got": sorted(bad),
                },
            )
        return vectors

    def _fail(self, exc: BaseException, started: float) -> AppError:
        error = map_provider_exception(exc, provider=self.provider_name)
        BREAKERS.get(self.resilience_key).record_failure(error)
        EMBEDDING_REQUESTS.labels(model=self.resilience_key, status=error.code).inc()
        EMBEDDING_LATENCY.labels(model=self.resilience_key).observe(time.perf_counter() - started)
        return error

    def _ok(self, started: float, count: int) -> None:
        BREAKERS.get(self.resilience_key).record_success()
        EMBEDDING_REQUESTS.labels(model=self.resilience_key, status="ok").inc()
        EMBEDDING_LATENCY.labels(model=self.resilience_key).observe(time.perf_counter() - started)
        logger.debug("embedded", extra={"model": self.resilience_key, "count": count})

    def embed_documents(
        self, texts: list[str], chunk_size: int | None = None, **kwargs: Any
    ) -> list[list[float]]:
        def once() -> list[list[float]]:
            BREAKERS.get(self.resilience_key).before_call()
            started = time.perf_counter()
            try:
                vectors = super(ResilientOpenAIEmbeddings, self).embed_documents(
                    texts, chunk_size=chunk_size, **kwargs
                )
            except Exception as exc:
                raise self._fail(exc, started) from exc
            self._ok(started, len(texts))
            return self._check(vectors)

        return retry_sync(once, attempts=EMBEDDING_ATTEMPTS, label=self.resilience_key)

    async def aembed_documents(
        self, texts: list[str], chunk_size: int | None = None, **kwargs: Any
    ) -> list[list[float]]:
        async def once() -> list[list[float]]:
            BREAKERS.get(self.resilience_key).before_call()
            started = time.perf_counter()
            try:
                vectors = await super(ResilientOpenAIEmbeddings, self).aembed_documents(
                    texts, chunk_size=chunk_size, **kwargs
                )
            except Exception as exc:
                raise self._fail(exc, started) from exc
            self._ok(started, len(texts))
            return self._check(vectors)

        return await retry_async(once, attempts=EMBEDDING_ATTEMPTS, label=self.resilience_key)

    def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed_documents([text], **kwargs)[0]

    async def aembed_query(self, text: str, **kwargs: Any) -> list[float]:
        return (await self.aembed_documents([text], **kwargs))[0]


def build_embeddings(settings: Settings) -> Embeddings:
    """Embeddings for ``EMBEDDING_PROVIDER``/``EMBEDDING_MODEL``."""
    provider, model = settings.embedding_provider, settings.embedding_model
    if provider == "hash":
        if settings.app_env != "test":
            raise ProviderError("the hash embedder is for tests only; set EMBEDDING_PROVIDER")
        return HashEmbeddings(dimensions=settings.embedding_dimensions)
    endpoints = {
        "euri": (settings.euri_base_url, settings.euri_api_key),
        "gemini": (settings.gemini_base_url, settings.gemini_api_key),
        "openai": (None, settings.openai_api_key),
    }
    if provider not in endpoints:
        raise ProviderError(f"embedding provider {provider!r} is not supported")
    base_url, key = endpoints[provider]
    if key is None:
        raise ProviderUnavailable(f"{provider} has no API key for embeddings")
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": key,
        "max_retries": 0,
        "timeout": settings.llm_timeout_seconds,
        "check_embedding_ctx_length": False,
        "chunk_size": 256,
        "resilience_key": f"{provider}:{model}",
        "provider_name": provider,
        "expected_dimensions": settings.embedding_dimensions,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ResilientOpenAIEmbeddings(**kwargs)
