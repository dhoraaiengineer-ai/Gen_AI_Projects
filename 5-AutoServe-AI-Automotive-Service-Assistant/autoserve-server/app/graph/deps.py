"""Node dependencies + the idempotent node runner (rules/60).

`run_node` gives every graph node the same contract:
  • input_hash = sha256(canonical JSON of what the node reads); (ro_id, node, input_hash) already stored in
    graph_node_runs → return the stored output, write nothing (trace outcome "cached");
  • otherwise run the node body in ONE transaction (its writes + the graph_node_runs row + an audit event commit
    together), with a timeout and at most 2 retries on transient errors (connection loss, timeout); any other
    failure, or a transient one that outlives the retries, halts the graph (checkpoint stays resumable);
  • always append one TraceEntry to execution_trace.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import Actor
from app.graph.state import ServiceGraphState
from app.models import GraphNodeRun
from app.rules.config import Rules, load_rules
from app.schemas.graph import TraceEntry
from app.services.audit import AuditService, canonical_json
from app.services.llm_service import LLM

log = structlog.get_logger(__name__)
MAX_RETRIES = 2
NODE_TIMEOUT_S = 90.0


@dataclass
class NodeDeps:
    sessionmaker: async_sessionmaker[AsyncSession]
    llm: LLM
    rules: Rules = field(default_factory=load_rules)
    today: Callable[[], date] = field(default=lambda: datetime.now(UTC).date())


Body = Callable[[AsyncSession], Awaitable[tuple[dict[str, Any], str]]]  # → (owned fields, trace outcome)


def input_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json({"v": data}).encode()).hexdigest()


def actor_of(state: ServiceGraphState) -> Actor:
    a = state.get("actor") or {}
    uid, did = a.get("user_id"), a.get("dealer_id")
    return Actor(
        user_id=uuid.UUID(uid) if uid else None, role=a.get("role", "system"), dealer_id=uuid.UUID(did) if did else None
    )


def _trace(node: str, started: float, at: datetime, outcome: str, h: str, note: str | None = None) -> dict[str, Any]:
    entry = TraceEntry(
        node=node,
        started_at=at,
        duration_ms=int((time.perf_counter() - started) * 1000),
        outcome=outcome,
        input_hash=h,
        note=note,
    )
    return entry.model_dump(mode="json")


async def run_node(
    deps: NodeDeps,
    state: ServiceGraphState,
    node: str,
    inputs: Any,
    body: Body,
    *,
    cache: bool = True,
    audit: bool = True,
) -> dict[str, Any]:
    """`audit=False` only for pure-read nodes (nothing is written, so there is nothing to audit)."""
    ro_id = uuid.UUID(state["ro_id"])
    h = input_hash(inputs)
    at, started = datetime.now(UTC), time.perf_counter()
    if cache:
        async with deps.sessionmaker() as s:
            stored = await s.scalar(
                select(GraphNodeRun.output).where(
                    GraphNodeRun.ro_id == ro_id, GraphNodeRun.node == node, GraphNodeRun.input_hash == h
                )
            )
        if stored is not None:
            return {**stored, "execution_trace": [_trace(node, started, at, "cached", h)]}

    attempt = 0
    while True:
        try:
            async with deps.sessionmaker() as s, s.begin():
                out, outcome = await asyncio.wait_for(body(s), timeout=NODE_TIMEOUT_S)
                if cache:
                    s.add(GraphNodeRun(ro_id=ro_id, node=node, input_hash=h, output=out))
                if audit:
                    await AuditService(s).record(
                        actor_of(state), f"graph.{node}", "repair_order", ro_id, {"input_hash": h, "outcome": outcome}
                    )
            return {**out, "execution_trace": [_trace(node, started, at, outcome, h)]}
        except (OperationalError, DBAPIError, TimeoutError) as exc:
            # Only connection loss / timeouts are transient. Constraint violations etc. are bugs or bad input: no retry.
            transient = isinstance(exc, (OperationalError, TimeoutError)) or bool(
                getattr(exc, "connection_invalidated", False)
            )
            attempt += 1
            log.warning("graph_node_retry", node=node, attempt=attempt, error=type(exc).__name__, transient=transient)
            if not transient or attempt > MAX_RETRIES:
                # Halt the graph (the next node must not run on a failed write, e.g. notify after record_decision).
                # The checkpoint keeps the thread resumable.
                raise


def node_inputs(state: ServiceGraphState, keys: tuple[str, ...], today: date) -> dict[str, Any]:
    """What a node's input hash covers. The RO status is excluded: no rule reads it, and the graph itself changes it
    (e.g. → INFO_PENDING), which would otherwise defeat idempotency on a re-run with unchanged data."""
    out: dict[str, Any] = {k: state.get(k) for k in keys} | {"day": today.isoformat()}
    if isinstance(out.get("intake"), dict):
        out["intake"] = {k: v for k, v in out["intake"].items() if k != "ro_status"}
    return out
