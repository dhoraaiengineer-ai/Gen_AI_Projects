"""In-process key-value store and a primary→fallback wrapper.

``FallbackKV`` uses the primary store (Redis) and switches to the in-process store when it fails,
retrying the primary after ``retry_after`` seconds — so Redis being down degrades shared state
(limits and memory become per-process) instead of failing requests.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from src.core.metrics import KV_FALLBACKS
from src.core.ports import KeyValueStore

logger = logging.getLogger(__name__)


class MemoryKV:
    name = "memory"

    def __init__(self, max_keys: int = 10_000, clock: Callable[[], float] = time.monotonic) -> None:
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.max_keys, self.clock = max_keys, clock

    def _live(self, key: str) -> Any:
        item = self._data.get(key)
        if item is None:
            return None
        if item[0] <= self.clock():
            del self._data[key]
            return None
        return item[1]

    def _put(self, key: str, value: Any, ttl: int, *, keep_expiry: bool = False) -> None:
        expires = self.clock() + ttl
        if keep_expiry and key in self._data:
            expires = self._data[key][0]
        self._data[key] = (expires, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_keys:
            self._data.popitem(last=False)

    async def get(self, key: str) -> str | None:
        value = self._live(key)
        return None if value is None else str(value)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._put(key, value, ttl_seconds)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        current = self._live(key)
        value = int(current or 0) + 1
        self._put(key, value, ttl_seconds, keep_expiry=current is not None)
        return value

    async def push(self, key: str, value: str, *, keep: int, ttl_seconds: int) -> None:
        items = list(self._live(key) or [])
        items.append(value)
        self._put(key, items[-keep:], ttl_seconds)

    async def items(self, key: str) -> list[str]:
        return list(self._live(key) or [])

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def ping(self) -> None:
        return None


class FallbackKV:
    def __init__(
        self,
        primary: KeyValueStore,
        fallback: KeyValueStore | None = None,
        *,
        retry_after: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.primary, self.fallback = primary, fallback or MemoryKV()
        self.retry_after, self.clock = retry_after, clock
        self._down_until = 0.0

    @property
    def name(self) -> str:
        return self.primary.name if self._down_until <= self.clock() else self.fallback.name

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if self._down_until <= self.clock():
            try:
                return await getattr(self.primary, method)(*args, **kwargs)
            except Exception as exc:
                self._down_until = self.clock() + self.retry_after
                KV_FALLBACKS.inc()
                logger.warning(
                    "kv primary failed; using in-process store",
                    extra={"store": self.primary.name, "error": type(exc).__name__},
                )
        return await getattr(self.fallback, method)(*args, **kwargs)

    async def get(self, key: str) -> str | None:
        result: str | None = await self._call("get", key)
        return result

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._call("set", key, value, ttl_seconds)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        result: int = await self._call("incr", key, ttl_seconds)
        return result

    async def push(self, key: str, value: str, *, keep: int, ttl_seconds: int) -> None:
        await self._call("push", key, value, keep=keep, ttl_seconds=ttl_seconds)

    async def items(self, key: str) -> list[str]:
        result: list[str] = await self._call("items", key)
        return result

    async def delete(self, key: str) -> None:
        await self._call("delete", key)

    async def ping(self) -> None:
        await self.primary.ping()  # readiness reports the real primary
