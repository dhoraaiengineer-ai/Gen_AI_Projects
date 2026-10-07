"""Per-user fixed-window rate limiting per endpoint group.

Backed by the shared key-value store (Redis) with an in-process fallback, so a Redis outage never fails a
request — limits just become per-replica.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.core.errors import RateLimited
from app.core.metrics import RATE_LIMITED
from app.core.ports import KeyValueStore

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateLimitResult:
    limit: int
    remaining: int
    reset_seconds: int

    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Reset": str(self.reset_seconds),
        }


class RateLimiter:
    def __init__(self, store: KeyValueStore, limits: dict[str, int]) -> None:
        self._store = store
        self._limits = limits

    async def check(self, group: str, user_id: str) -> RateLimitResult:
        limit = self._limits.get(group, self._limits["default"])
        now = int(time.time())
        window = now // WINDOW_SECONDS
        reset = WINDOW_SECONDS - (now % WINDOW_SECONDS)
        key = f"ratelimit:{group}:{user_id}:{window}"
        count = await self._store.incr(key, ttl_seconds=WINDOW_SECONDS + 5)
        result = RateLimitResult(limit=limit, remaining=limit - count, reset_seconds=reset)
        if count > limit:
            RATE_LIMITED.labels(group).inc()
            logger.info("rate limited", extra={"group": group, "count": count, "limit": limit})
            raise RateLimited(retry_after=reset)
        return result
