"""FastAPI dependencies for the service graph (overridable in tests)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends

from app.api.deps import get_llm
from app.core.db import get_sessionmaker
from app.graph.deps import NodeDeps
from app.graph.workflow import postgres_checkpointer
from app.services.llm_service import LLM


def get_node_deps(llm: LLM = Depends(get_llm)) -> NodeDeps:
    return NodeDeps(sessionmaker=get_sessionmaker(), llm=llm)


async def get_saver() -> AsyncIterator[Any]:
    """A checkpointer per request: its psycopg pool lives on the request's event loop (safe across loops/tests)."""
    async with postgres_checkpointer() as saver:
        yield saver
