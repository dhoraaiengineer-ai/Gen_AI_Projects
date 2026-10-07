"""In-process key-value store: the fallback when Redis is unavailable, and the fake used in tests."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class InMemoryKV:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lists: dict[str, tuple[deque[str], float | None]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _expiry(ttl: int | None) -> float | None:
        return time.monotonic() + ttl if ttl else None

    @staticmethod
    def _alive(expiry: float | None) -> bool:
        return expiry is None or expiry > time.monotonic()

    async def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None or not self._alive(item[1]):
            self._data.pop(key, None)
            return None
        return item[0]

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data[key] = (value, self._expiry(ttl_seconds))

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._lists.pop(key, None)

    async def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        async with self._lock:
            current = await self.get(key)
            value = int(current or 0) + 1
            expiry = self._data[key][1] if current is not None else self._expiry(ttl_seconds)
            self._data[key] = (str(value), expiry)
            return value

    async def lpush_trim(self, key: str, value: str, max_len: int, ttl_seconds: int | None = None) -> None:
        items, _ = self._lists.get(key, (deque(), None))
        items.appendleft(value)
        while len(items) > max_len:
            items.pop()
        self._lists[key] = (items, self._expiry(ttl_seconds))

    async def lrange(self, key: str, count: int) -> list[str]:
        entry = self._lists.get(key)
        if entry is None or not self._alive(entry[1]):
            return []
        return list(entry[0])[:count]
