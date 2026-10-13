"""Stale-while-revalidate cache: hit, stale refresh, expiry, single flight."""

from __future__ import annotations

import asyncio

from src.core.cache import SWRCache


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_fresh_stale_and_expired() -> None:
    clock = Clock()
    cache = SWRCache("t", ttl=10, stale_ttl=100, clock=clock)
    calls: list[int] = []

    async def compute() -> int:
        calls.append(1)
        return len(calls)

    assert await cache.get_or_compute("k", compute) == 1
    clock.now = 5
    assert await cache.get_or_compute("k", compute) == 1  # fresh
    clock.now = 50
    assert await cache.get_or_compute("k", compute) == 1  # stale value served, refresh scheduled
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(calls) == 2
    clock.now = 51
    assert await cache.get_or_compute("k", compute) == 2  # refreshed value
    clock.now = 500
    assert await cache.get_or_compute("k", compute) == 3  # expired → recomputed inline


async def test_single_flight_for_concurrent_misses() -> None:
    cache = SWRCache("t")
    calls: list[int] = []

    async def compute() -> str:
        calls.append(1)
        await asyncio.sleep(0.01)
        return "v"

    results = await asyncio.gather(*(cache.get_or_compute("k", compute) for _ in range(5)))
    assert results == ["v"] * 5
    assert len(calls) == 1


async def test_keys_are_independent_and_invalidation_works() -> None:
    cache = SWRCache("t")

    async def a() -> str:
        return "a"

    async def b() -> str:
        return "b"

    assert await cache.get_or_compute(("tenant-1", "PF-A"), a) == "a"
    assert await cache.get_or_compute(("tenant-2", "PF-A"), b) == "b"
    cache.invalidate(("tenant-1", "PF-A"))
    assert await cache.get_or_compute(("tenant-1", "PF-A"), b) == "b"
