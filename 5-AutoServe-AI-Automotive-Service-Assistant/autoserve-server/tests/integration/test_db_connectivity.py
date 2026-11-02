"""Real-Postgres smoke test. Runs in CI against the pgvector service container (TEST_DATABASE_URL)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.db import engine_kwargs

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set (provided by CI / compose) — P1-1")
async def test_postgres_has_pgvector_available() -> None:
    url = (TEST_DATABASE_URL or "").replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, **engine_kwargs("direct", 5))
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT 1"))).scalar() == 1
            available = await conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"))
            assert available.scalar() == 1
    finally:
        await engine.dispose()
