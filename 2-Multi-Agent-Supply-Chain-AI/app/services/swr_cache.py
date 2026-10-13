"""Stale-while-revalidate cache for expensive read models (dashboard, logistics summary, agent stats).

Fresh values are served from memory; stale values are served instantly while one background task refreshes them.
Only the very first request (or one after an invalidation with no stale value) waits for the computation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class SwrCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._values: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    async def get(self, key: str, compute: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._values.get(key)
        if hit is not None:
            if time.monotonic() - hit[0] >= self._ttl and not (key in self._tasks and not self._tasks[key].done()):
                self._tasks[key] = asyncio.create_task(self._refresh(key, compute))
            return hit[1]
        return await self._refresh(key, compute)

    async def _refresh(self, key: str, compute: Callable[[], Awaitable[Any]]) -> Any:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            hit = self._values.get(key)
            if hit is not None and time.monotonic() - hit[0] < self._ttl:
                return hit[1]
            started = time.perf_counter()
            try:
                value = await compute()
            except Exception:
                if hit is not None:
                    logger.exception("refresh failed — serving stale value", extra={"key": key})
                    return hit[1]
                raise
            self._values[key] = (time.monotonic(), value)
            logger.info("read model refreshed", extra={"key": key, "ms": round((time.perf_counter() - started) * 1000)})
            return value

    def invalidate(self, prefix: str = "") -> None:
        """Mark entries stale (they keep serving until refreshed)."""
        for key, (_, value) in list(self._values.items()):
            if key.startswith(prefix):
                self._values[key] = (0.0, value)
