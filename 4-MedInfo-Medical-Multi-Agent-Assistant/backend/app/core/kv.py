"""Key-value store used for caches, short-term memory and rate limits. Redis in production
(app/rag/providers.py: RedisKV); this in-process fallback is used when REDIS_URL is unset."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Protocol


class KeyValueStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        """Increment; the TTL is set when the key is created (fixed-window counters)."""
        ...

    def ttl(self, key: str) -> int: ...

    def list_push(self, key: str, value: str, max_len: int, ttl_seconds: int | None = None) -> None: ...

    def list_range(self, key: str) -> list[str]: ...

    def ping(self) -> bool: ...


class InProcessKV:
    """Thread-safe dict with TTLs. Per-process only: fine locally, not shared across replicas."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._data: dict[str, tuple[object, float | None]] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def _live(self, key: str) -> object | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and self._clock() >= expires:
            del self._data[key]
            return None
        return value

    def _exp(self, ttl: int | None) -> float | None:
        return self._clock() + ttl if ttl else None

    def get(self, key: str) -> str | None:
        with self._lock:
            v = self._live(key)
            return v if isinstance(v, str) else None

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        with self._lock:
            self._data[key] = (value, self._exp(ttl_seconds))

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        with self._lock:
            current = self._live(key)
            if current is None:
                self._data[key] = ("1", self._exp(ttl_seconds))
                return 1
            n = int(str(current)) + 1
            self._data[key] = (str(n), self._data[key][1])
            return n

    def ttl(self, key: str) -> int:
        with self._lock:
            if self._live(key) is None:
                return -2
            expires = self._data[key][1]
            return -1 if expires is None else max(0, int(expires - self._clock()))

    def list_push(self, key: str, value: str, max_len: int, ttl_seconds: int | None = None) -> None:
        with self._lock:
            current = self._live(key)
            items = list(current) if isinstance(current, list) else []
            items.append(value)
            self._data[key] = (items[-max_len:], self._exp(ttl_seconds))

    def list_range(self, key: str) -> list[str]:
        with self._lock:
            current = self._live(key)
            return list(current) if isinstance(current, list) else []

    def ping(self) -> bool:
        return True
