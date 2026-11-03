"""Per-IP rate limiter for the public, unauthenticated marketing chat
endpoint (app/routes/marketing.py). No reusable inbound rate limiter
exists elsewhere in this codebase (RATE_LIMIT_PER_MINUTE in .env is
unused dead config) -- this is a small, purpose-built Redis fixed-window
limiter, not a general-purpose middleware.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]

RATE_LIMIT_WINDOW_SECONDS = 60


def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class MarketingRateLimitError(Exception):
    """Raised when a visitor IP exceeds the marketing chat rate limit, or
    when Redis is unreachable -- this endpoint fails closed since it's a
    public, cost-bearing LLM call with no other spend guard upstream."""


async def check_marketing_chat_rate_limit(client_ip: str) -> None:
    """Fixed-window limiter: MARKETING_CHAT_RATE_LIMIT_PER_MINUTE requests
    per IP per 60s window. Raises MarketingRateLimitError if the limit
    is exceeded or Redis can't be reached."""

    limit = settings.marketing_chat_rate_limit_per_minute
    key = f"marketing_chat_rl:{client_ip}"

    try:
        redis = _get_redis()
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)
    except Exception as exc:
        raise MarketingRateLimitError("Rate limiter is temporarily unavailable. Please try again shortly.") from exc

    if current > limit:
        raise MarketingRateLimitError(f"Too many requests -- limit is {limit} per minute. Please wait and try again.")
