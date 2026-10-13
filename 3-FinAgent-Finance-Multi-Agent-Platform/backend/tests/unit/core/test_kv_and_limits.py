"""Key-value stores (memory, Redis→memory fallback), rate limits and conversation memory."""

from __future__ import annotations

from typing import Any

import pytest

from src.core.errors import RateLimited
from src.core.kv import FallbackKV, MemoryKV
from src.core.rate_limit import Limit, RateLimiter
from src.orchestration.memory import ConversationMemory


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


class BrokenKV(MemoryKV):
    name = "redis"

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.broken = True

    async def incr(self, key: str, ttl_seconds: int) -> int:
        self.calls += 1
        if self.broken:
            raise ConnectionError("redis down")
        return await super().incr(key, ttl_seconds)


async def test_memory_kv_expiry_counters_and_lists() -> None:
    clock = Clock()
    kv = MemoryKV(clock=clock)
    await kv.set("a", "1", 10)
    assert await kv.incr("n", 10) == 1 and await kv.incr("n", 10) == 2
    for i in range(5):
        await kv.push("l", str(i), keep=3, ttl_seconds=10)
    assert await kv.items("l") == ["2", "3", "4"]
    clock.now += 11
    assert await kv.get("a") is None and await kv.items("l") == []
    assert await kv.incr("n", 10) == 1  # expired counter starts again


async def test_fallback_switches_and_retries_primary() -> None:
    clock = Clock()
    primary = BrokenKV()
    kv = FallbackKV(primary, MemoryKV(clock=clock), retry_after=30, clock=clock)
    assert await kv.incr("k", 60) == 1  # served by the fallback
    assert kv.name == "memory" and primary.calls == 1
    assert await kv.incr("k", 60) == 2 and primary.calls == 1  # primary not retried yet
    primary.broken = False
    clock.now += 31
    assert await kv.incr("k", 60) == 1 and kv.name == "redis"  # primary is back


async def test_rate_limiter_blocks_then_resets_per_window() -> None:
    clock = Clock()
    limiter = RateLimiter(MemoryKV(clock=clock), {"chat": Limit(2, 60)}, clock=clock)
    first = await limiter.check("t", "u", "chat")
    assert first.remaining == 1 and first.headers()["X-RateLimit-Limit"] == "2"
    await limiter.check("t", "u", "chat")
    with pytest.raises(RateLimited) as exc:
        await limiter.check("t", "u", "chat")
    assert exc.value.retry_after and 1 <= exc.value.retry_after <= 60
    assert (await limiter.check("t", "other-user", "chat")).remaining == 1  # per user
    clock.now += 60
    assert (await limiter.check("t", "u", "chat")).remaining == 1


class FailingStore:
    async def ensure(self, conversation_id: str | None, user_id: str, title: str) -> str:
        raise ConnectionError("db down")

    async def add(self, *args: Any, **kwargs: Any) -> None:
        raise ConnectionError("db down")


async def test_conversation_memory_round_trip_and_never_raises() -> None:
    memory = ConversationMemory(MemoryKV(), FailingStore())
    cid = await memory.start("c1", "u1", "Why did risk rise?")
    assert cid == "c1"  # store down → caller id kept
    report = {"requestId": "r1", "intent": "portfolio_risk", "portfolio": "PF-A", "tickers": []}
    await memory.remember("t", cid, "Why did risk rise?", report)
    history = await memory.history("t", cid)
    assert history[0]["portfolio"] == "PF-A" and history[0]["intent"] == "portfolio_risk"
    assert await memory.history("other-tenant", cid) == []
    assert await memory.history("t", None) == []
