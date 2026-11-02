"""Async SQLAlchemy engine/session (ADR-007: Supabase pooler aware)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def engine_kwargs(pooler_mode: str, connect_timeout_s: float, null_pool: bool = False) -> dict[str, Any]:
    connect_args: dict[str, Any] = {"timeout": connect_timeout_s}
    if pooler_mode == "transaction":
        # Supabase transaction pooler (port 6543) does not support prepared statements.
        connect_args["statement_cache_size"] = 0
    kwargs: dict[str, Any] = {"pool_pre_ping": True, "connect_args": connect_args}
    if null_pool:
        kwargs["poolclass"] = NullPool
    return kwargs


@lru_cache
def get_engine() -> AsyncEngine:
    s = get_settings()
    return create_async_engine(
        s.database_url, **engine_kwargs(s.database_pooler_mode, s.db_connect_timeout_s, s.db_use_null_pool)
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


def reset_db_caches() -> None:
    """Drop cached engine/sessionmaker (tests, settings changes)."""
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
