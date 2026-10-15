"""Per-user fixed-window rate limits with Retry-After (Redis-backed in production)."""

from __future__ import annotations

import logging

from app.core.errors import AppError
from app.core.kv import KeyValueStore
from app.core.metrics import RATE_LIMITED

logger = logging.getLogger(__name__)


class RateLimitedError(AppError):
    status_code = 429
    public_message = "Too many requests. Please wait a moment and try again."


class RateLimiter:
    def __init__(self, kv: KeyValueStore, limits: dict[str, tuple[int, int]]) -> None:
        """limits: bucket -> (max requests, window seconds)."""
        self._kv = kv
        self._limits = limits

    def check(self, bucket: str, user_id: str) -> None:
        limit, window = self._limits[bucket]
        key = f"medinfo:rl:{bucket}:{user_id}"
        try:
            count = self._kv.incr(key, ttl_seconds=window)
        except Exception as exc:  # a cache outage must not take the API down
            logger.warning("rate limiter unavailable; allowing", extra={"error": type(exc).__name__})
            return
        if count > limit:
            retry = self._kv.ttl(key)
            RATE_LIMITED.labels(bucket).inc()
            logger.info("rate limited", extra={"bucket": bucket, "limit": limit})
            raise RateLimitedError(retry_after=retry if retry > 0 else window)
