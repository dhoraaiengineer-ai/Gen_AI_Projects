"""Service graph (P3-3): intake → vehicle_context → document → diagnosis → warranty → estimate → risk → route.

route → info_pending → END | recall_job → END | human_review (interrupt) → record_decision → notify → END
Claim review graph (thread "claim:{id}"): human_review(warranty_decision) → record_decision → notify → END.

Checkpointer: langgraph PostgresSaver on a psycopg pool (MemorySaver only in unit tests); its tables are created by
Alembic. psycopg's async driver needs a selector event loop on Windows (see `use_selector_loop`).
"""

from __future__ import annotations

import asyncio
import itertools
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings
from app.graph import routing
from app.graph.deps import NodeDeps, input_hash
from app.graph.nodes import (
    diagnosis,
    document,
    estimate,
    human_review,
    notify,
    outcomes,
    record_decision,
    risk,
    ro_intake,
    vehicle_context,
    warranty,
)
from app.graph.state import ServiceGraphState
from app.schemas.graph import TraceEntry

Node = Callable[[ServiceGraphState, NodeDeps], Awaitable[dict[str, Any]]]


def use_selector_loop() -> None:
    """psycopg async cannot run on Windows' default Proactor loop."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def plain_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def postgres_checkpointer(url: str | None = None) -> AsyncIterator[AsyncPostgresSaver]:
    pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
        plain_url(url or get_settings().database_url),
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        min_size=1,
        max_size=5,
        open=False,
    )
    await pool.open()
    try:
        # Tables come from Alembic (g7b8c9d0e105). setup() is NOT called: its CREATE INDEX CONCURRENTLY waits for
        # every open transaction and deadlocked inside API requests (MEMORY L-010).
        yield AsyncPostgresSaver(pool)
    finally:
        await pool.close()


def _bind(fn: Node, deps: NodeDeps) -> Any:  # LangGraph's add_node overloads do not accept a plain async callable type
    async def node(state: ServiceGraphState) -> dict[str, Any]:
        return await fn(state, deps)

    return node


def _route_node(deps: NodeDeps) -> Any:
    async def node(state: ServiceGraphState) -> dict[str, Any]:
        started = datetime.now(UTC)
        out = routing.route(state, deps.rules)
        trace = TraceEntry(
            node="route",
            started_at=started,
            duration_ms=0,
            outcome="ok",
            input_hash=input_hash(out.model_dump()),
            note=out.next,
        )
        return {"route": out.model_dump(mode="json"), "execution_trace": [trace.model_dump(mode="json")]}

    return node


def _review_tail(g: StateGraph[ServiceGraphState], deps: NodeDeps) -> None:
    g.add_node("human_review", _bind(human_review.run, deps))
    g.add_node("record_decision", _bind(record_decision.run, deps))
    g.add_node("notify", _bind(notify.run, deps))
    g.add_edge("human_review", "record_decision")
    g.add_edge("record_decision", "notify")
    g.add_edge("notify", END)


def build_service_graph(deps: NodeDeps, checkpointer: BaseCheckpointSaver[Any] | None) -> CompiledStateGraph[Any]:
    g: StateGraph[ServiceGraphState] = StateGraph(ServiceGraphState)
    chain: list[tuple[str, Node]] = [
        ("intake", ro_intake.run),
        ("vehicle_context", vehicle_context.run),
        ("document", document.run),
        ("diagnosis", diagnosis.run),
        ("warranty", warranty.run),
        ("estimate", estimate.run),
        ("risk", risk.run),
    ]
    for name, fn in chain:
        g.add_node(name, _bind(fn, deps))
    g.add_node("route", _route_node(deps))
    g.add_node("info_pending", _bind(outcomes.info_pending, deps))
    g.add_node("recall_job", _bind(outcomes.recall_job, deps))
    _review_tail(g, deps)

    g.add_edge(START, "intake")
    for (a, _), (b, _) in itertools.pairwise(chain):
        g.add_edge(a, b)
    g.add_edge("risk", "route")
    g.add_conditional_edges(
        "route",
        lambda s: s["route"]["next"],
        {"info_pending": "info_pending", "recall_job": "recall_job", "human_review": "human_review", "stop": END},
    )
    g.add_edge("info_pending", END)
    g.add_edge("recall_job", END)
    return g.compile(checkpointer=checkpointer)


def build_claim_graph(deps: NodeDeps, checkpointer: BaseCheckpointSaver[Any] | None) -> CompiledStateGraph[Any]:
    g: StateGraph[ServiceGraphState] = StateGraph(ServiceGraphState)
    _review_tail(g, deps)
    g.add_edge(START, "human_review")
    return g.compile(checkpointer=checkpointer)
