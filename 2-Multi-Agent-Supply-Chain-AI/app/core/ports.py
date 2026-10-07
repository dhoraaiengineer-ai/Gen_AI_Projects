"""Interfaces (ports) for external providers.

Concrete adapters live only in `app/rag/providers.py` and are wired in `app/container.py`. Everything
else depends on these protocols, so tests use in-memory fakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class KeyValueStore(Protocol):
    """Shared cache / counters (Redis in production, in-process fallback)."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def incr(self, key: str, ttl_seconds: int | None = None) -> int: ...

    async def lpush_trim(self, key: str, value: str, max_len: int, ttl_seconds: int | None = None) -> None: ...

    async def lrange(self, key: str, count: int) -> list[str]: ...


class Embedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


@dataclass
class OcrResult:
    text: str
    confidence: float  # 0-100
    engine: str


class OcrEngine(Protocol):
    name: str

    def image_to_text(self, image_bytes: bytes) -> OcrResult: ...


@dataclass
class WebResult:
    title: str
    url: str
    content: str
    score: float = 0.0


@dataclass
class WebSearchResponse:
    query: str
    results: list[WebResult] = field(default_factory=list)


class WebSearch(Protocol):
    async def search(self, query: str, max_results: int = 5) -> WebSearchResponse: ...
