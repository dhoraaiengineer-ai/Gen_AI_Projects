"""Redis key-value adapter (the only module importing the redis SDK)."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis


class RedisKV:
    name = "redis"

    def __init__(self, url: str, *, timeout: float = 2.0) -> None:
        self._client: Any = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=timeout,
            socket_connect_timeout=timeout,
            health_check_interval=30,
        )

    async def get(self, key: str) -> str | None:
        value = await self._client.get(key)
        return None if value is None else str(value)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._client.set(key, value, ex=ttl_seconds)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, ttl_seconds, nx=True)
            value, _ = await pipe.execute()
        return int(value)

    async def push(self, key: str, value: str, *, keep: int, ttl_seconds: int) -> None:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, value)
            pipe.ltrim(key, -keep, -1)
            pipe.expire(key, ttl_seconds)
            await pipe.execute()

    async def items(self, key: str) -> list[str]:
        return [str(v) for v in await self._client.lrange(key, 0, -1)]

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def ping(self) -> None:
        await self._client.ping()

    async def aclose(self) -> None:
        await self._client.aclose()
