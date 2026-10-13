"""In-process stale-while-revalidate cache with single-flight computation.

* fresh (age < ``ttl``)            → cached value
* stale (ttl ≤ age < ``stale_ttl``) → cached value now, one background refresh
* expired / missing                → compute (concurrent callers share one computation)

Keys must include the tenant (ADR-026). A Redis-backed variant arrives with Stage 8; the interface
stays the same.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Any

from src.core.metrics import CACHE_EVENTS

logger = logging.getLogger(__name__)


@dataclass
class _Entry:
    value: Any
    stored_at: float


class SWRCache:
    def __init__(
        self,
        name: str,
        *,
        ttl: float = 300.0,
        stale_ttl: float = 3600.0,
        max_entries: int = 512,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.ttl, self.stale_ttl, self.max_entries = ttl, stale_ttl, max_entries
        self.clock = clock
        self._entries: dict[Hashable, _Entry] = {}
        self._inflight: dict[Hashable, asyncio.Task[Any]] = {}

    async def get_or_compute[T](self, key: Hashable, compute: Callable[[], Awaitable[T]]) -> T:
        entry = self._entries.get(key)
        now = self.clock()
        if entry is not None:
            age = now - entry.stored_at
            if age < self.ttl:
                CACHE_EVENTS.labels(cache=self.name, event="hit").inc()
                return entry.value  # type: ignore[no-any-return]
            if age < self.stale_ttl:
                CACHE_EVENTS.labels(cache=self.name, event="stale").inc()
                self._refresh(key, compute)
                return entry.value  # type: ignore[no-any-return]
        CACHE_EVENTS.labels(cache=self.name, event="miss").inc()
        return await self._refresh(key, compute)  # type: ignore[no-any-return]

    def _refresh(self, key: Hashable, compute: Callable[[], Awaitable[Any]]) -> asyncio.Task[Any]:
        task = self._inflight.get(key)
        if task is None or task.done():
            task = asyncio.ensure_future(self._compute(key, compute))
            self._inflight[key] = task
        return task

    async def _compute(self, key: Hashable, compute: Callable[[], Awaitable[Any]]) -> Any:
        try:
            value = await compute()
        except Exception:
            logger.warning("cache refresh failed", extra={"cache": self.name}, exc_info=True)
            raise
        finally:
            self._inflight.pop(key, None)
        if len(self._entries) >= self.max_entries:
            oldest = min(self._entries, key=lambda k: self._entries[k].stored_at)
            self._entries.pop(oldest, None)
        self._entries[key] = _Entry(value, self.clock())
        return value

    def invalidate(self, key: Hashable | None = None) -> None:
        if key is None:
            self._entries.clear()
        else:
            self._entries.pop(key, None)
