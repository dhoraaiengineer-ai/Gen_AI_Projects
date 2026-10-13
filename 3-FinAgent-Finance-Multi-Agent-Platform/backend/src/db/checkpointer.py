"""LangGraph Postgres checkpointer on the session pooler (5432).

Runs paused for human approval are stored here so a decision can resume them after a restart or
on another API instance. Tables come from migration 0004 (RLS enabled); ``setup()`` only verifies
they are at the expected version.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


def _libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


class Checkpointer:
    """Owns the connection pool; ``saver`` is what ``StateGraph.compile`` takes."""

    def __init__(self, url: str, *, max_size: int = 4) -> None:
        self._pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
            _libpq_url(url),
            min_size=1,
            max_size=max_size,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
        )
        self.saver = AsyncPostgresSaver(self._pool)

    async def start(self) -> AsyncPostgresSaver:
        await self._pool.open(wait=True, timeout=30)
        await self.saver.setup()  # no-op when migration 0004 is applied
        logger.info("checkpointer ready")
        return self.saver

    async def aclose(self) -> None:
        await self._pool.close()
