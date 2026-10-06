"""Per-user rate limiting for the endpoints that spend LLM / embedding quota.

Sliding window per (bucket, user): at most `limit` requests in any `window_seconds`. State is in memory,
so limits apply per process. That matches the deployment (one uvicorn worker per pod), but with N replicas
a user can get up to N x the limit; a shared store (Redis) would be needed to make it exact.
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

# Drop idle users' state once this many keys are tracked, so memory stays bounded.
_PRUNE_AT = 10_000


@dataclass(frozen=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds until the next request is allowed (0 when allowed)


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()  # sync route handlers run in a threadpool

    def hit(self, key: str) -> Decision:
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(hits[0] + self.window - now + 0.999))
                return Decision(False, self.limit, 0, retry_after)
            hits.append(now)
            if len(self._hits) > _PRUNE_AT:
                self._prune(now)
            return Decision(True, self.limit, self.limit - len(hits), 0)

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
            del self._hits[key]
