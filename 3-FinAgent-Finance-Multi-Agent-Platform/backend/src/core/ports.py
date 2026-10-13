"""Ports: interfaces the domain depends on; adapters live in ``src/providers`` and ``src/data``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published: date | None
    source: str
    summary: str
    tickers: tuple[str, ...] = ()
    sentiment: float | None = None  # -1 (negative) … +1 (positive), None if unknown
    provider: str = ""


class NewsProvider(Protocol):
    name: str

    async def search(
        self, query: str, *, tickers: tuple[str, ...] = (), limit: int = 5
    ) -> list[NewsItem]: ...


# ---------------------------------------------------------------- decision models (ADR-027)
@dataclass(frozen=True)
class Decision:
    """One typed answer: label (choice), expected score (score) or P(yes) (noul)."""

    kind: str  # noul | choice | score
    value: str | float
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    provider: str = ""


@dataclass(frozen=True)
class DecisionResult:
    answers: dict[str, Decision]
    provider: str
    model: str
    latency_ms: float
    input_tokens: int = 0


class DecisionModel(Protocol):
    """Fast typed decisions (choice / score / yes-no) — e.g. TypeSafe AI's Jev."""

    name: str

    async def decide(
        self, state: object, questions: dict[str, dict[str, object]]
    ) -> DecisionResult: ...


# ---------------------------------------------------------------- key-value store (Stage 8)
class KeyValueStore(Protocol):
    """Short-lived shared state: rate-limit counters, conversation memory, cached answers.

    Implemented by Redis (``src/providers/kv.py``) and an in-process store (``src/core/kv.py``).
    Keys always include the tenant (ADR-026).
    """

    @property
    def name(self) -> str: ...

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    async def incr(self, key: str, ttl_seconds: int) -> int: ...

    async def push(self, key: str, value: str, *, keep: int, ttl_seconds: int) -> None: ...

    async def items(self, key: str) -> list[str]: ...

    async def delete(self, key: str) -> None: ...

    async def ping(self) -> None: ...
