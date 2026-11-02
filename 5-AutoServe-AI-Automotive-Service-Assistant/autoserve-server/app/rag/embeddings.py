"""Embedding providers (ADR-008): EURI text-embedding-3-small (1536-d) or an offline hashing embedder for tests."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from app.core.config import Settings, get_settings
from app.core.errors import LlmUnavailable

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class EuriEmbedder:
    def __init__(self, settings: Settings) -> None:
        base_url, key = settings.provider_credentials("euri")
        if key is None:
            raise LlmUnavailable("Embedding provider is not configured.")
        self.dimensions = settings.embedding_dimensions
        self._client = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_base=base_url,
            openai_api_key=key,
            dimensions=settings.embedding_dimensions,
            max_retries=settings.llm_max_retries,
            request_timeout=settings.llm_timeout_s,
            chunk_size=64,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = await self._client.aembed_documents(texts)
        except Exception as exc:  # quota / network / auth → one typed error (no embedding fallback, ADR-008)
            raise LlmUnavailable("The manual search service is temporarily unavailable.") from exc
        self._check(vectors)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        try:
            vector = await self._client.aembed_query(text)
        except Exception as exc:
            raise LlmUnavailable("The manual search service is temporarily unavailable.") from exc
        self._check([vector])
        return vector

    def _check(self, vectors: list[list[float]]) -> None:
        if any(len(v) != self.dimensions for v in vectors):
            raise LlmUnavailable("Embedding dimension mismatch (ADR-008).")


class HashingEmbedder:
    """Deterministic bag-of-words hashing embedder. Offline; gives lexical similarity only. Tests / CI only."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in _TOKEN.findall(text.lower()):
            h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
            vec[h % self.dimensions] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embedder(settings: Settings | None = None) -> Embedder:
    s = settings or get_settings()
    if s.embedding_provider == "hashing":
        return HashingEmbedder(s.embedding_dimensions)
    return EuriEmbedder(s)
