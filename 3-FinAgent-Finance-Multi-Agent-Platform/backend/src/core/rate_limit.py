"""Per-user fixed-window rate limits per endpoint group (chat, analyze, read, upload).

Keys: ``rl:{tenant}:{user}:{group}:{window}``. Over the limit raises :class:`RateLimited` with
``retry_after``; the decision also carries the ``X-RateLimit-*`` header values.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from src.core.errors import RateLimited
from src.core.metrics import RATE_LIMITED
from src.core.ports import KeyValueStore


@dataclass(frozen=True)
class Limit:
    requests: int
    window_seconds: int


@dataclass(frozen=True)
class RateDecision:
    limit: int
    remaining: int
    reset_epoch: int

    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_epoch),
        }


class RateLimiter:
    def __init__(
        self,
        kv: KeyValueStore,
        limits: dict[str, Limit],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.kv, self.limits, self.clock = kv, limits, clock

    async def check(self, tenant_id: str, user_id: str, group: str) -> RateDecision:
        limit = self.limits[group]
        now = self.clock()
        window = int(now // limit.window_seconds)
        reset = (window + 1) * limit.window_seconds
        count = await self.kv.incr(
            f"rl:{tenant_id}:{user_id}:{group}:{window}", limit.window_seconds + 5
        )
        decision = RateDecision(limit.requests, max(limit.requests - count, 0), reset)
        if count > limit.requests:
            RATE_LIMITED.labels(group=group).inc()
            retry = max(1, int(reset - now))
            raise RateLimited(
                f"Too many {group} requests; try again in {retry} s.", retry_after=retry
            )
        return decision
