"""LangGraph orchestration runtime — 9-agent AutoRAG loop.

Assembles the StateGraph with all nodes and conditional edges.
Each node is a stateless async function imported from its agent module.

See:
  .claude/rules/workflow-contracts.md — orchestration contracts
  .claude/rules/graph-state-governance.md — GraphState rules
  .claude/specs/agents/ — per-agent interface contracts
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.core.state import GraphState

# All 9 agent nodes — wired directly, no stub forwarders
from app.graph.nodes.builder import builder_node
from app.graph.nodes.compressor import compressor_node
from app.graph.nodes.deployer import deployer_node
from app.graph.nodes.diagnoser import diagnoser_node
from app.graph.nodes.evaluator import evaluator_node
from app.graph.nodes.improver import improver_node
from app.graph.nodes.ingestion import ingestion_node
from app.graph.nodes.observer import observer_node
from app.graph.nodes.query_rewriter import query_rewriter_node

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: F401

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# HITL approval gate — pauses the graph until a reviewer approves via
# POST /api/v1/approve/{run_id}
# ──────────────────────────────────────────────────────────────────────────────

import datetime as _dt
import uuid as _uuid


async def _hitl_approval_node(state: GraphState) -> GraphState:
    """HITL approval gate: pause graph execution via LangGraph interrupt().

    This node is reached when 0.70 <= unified_score < 0.85 (see _route_after_evaluator).

    How it works:
      - `interrupt()` suspends the LangGraph thread at this node, serialising
        the current GraphState to the checkpoint saver (PostgresSaver).
      - The FastAPI endpoint POST /api/v1/approve/{run_id} resumes the thread
        by calling `graph.update_state(config, {"approval_status": "approved"})`
        and then streaming/invoking the graph again from the checkpoint.
      - If approval is denied, `approval_status="rejected"` causes this node to
        route to observer (retry loop).

    Notifications (SendGrid + Twilio) are sent by the API route handler that
    processes the approval request, not here in the node -- keeping this node
    stateless per workflow-contracts.md Rule 2.

    Raises:
      GraphInterrupt: when interrupt() is called -- LangGraph catches this and
                      persists the checkpoint. This is expected, not an error.
    """
    from langgraph.types import interrupt  # local import -- only used here

    unified_score = state.get("unified_score") or 0.0
    x_trace_id = state.get("x_trace_id") or str(_uuid.uuid4())
    run_id = state.get("run_id") or ""

    logger.info(
        "hitl_approval_requested",
        extra={
            "unified_score": unified_score,
            "run_id": run_id,
            "x_trace_id": x_trace_id,
        },
    )

    # Record the pending-approval state so the approver API can read it
    timestamp = _dt.datetime.utcnow().isoformat() + "Z"

    # interrupt() pauses execution here. LangGraph serialises state and raises
    # GraphInterrupt -- the caller (FastAPI) catches it and returns a 202 to the
    # client with the job_id/run_id so they can poll for completion.
    approved: bool = interrupt(
        {
            "reason": "unified_score_below_deploy_threshold",
            "unified_score": unified_score,
            "run_id": run_id,
            "requested_at": timestamp,
        }
    )

    if approved:
        logger.info(
            "hitl_approval_granted",
            extra={"run_id": run_id, "x_trace_id": x_trace_id},
        )
        return {
            **state,
            "approval_status": "approved",
            "updated_at": timestamp,
        }

    logger.warning(
        "hitl_approval_denied",
        extra={"run_id": run_id, "x_trace_id": x_trace_id},
    )
    return {
        **state,
        "approval_status": "rejected",
        "updated_at": timestamp,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Conditional edge routing functions
# ──────────────────────────────────────────────────────────────────────────────


def _route_after_evaluator(state: GraphState) -> str:
    """Route after Evaluator. Priority order is FIXED.

    1. Safety override (guardrail_blocked) — highest priority
    2. Faithfulness hard block (< 0.5) — non-bypassable
    3. Adversarial block (pass_rate < 1.0)
    4. Deploy gate (>= 0.85)
    5. HITL gate (0.70–0.84)
    6. Retry loop (< 0.70)
    """
    if state.get("guardrail_blocked"):
        return END  # type: ignore[return-value]

    # 2. Faithfulness hard block — non-bypassable (ai-guardrails.md Rule 13: fail closed)
    faithfulness = state.get("faithfulness")
    if faithfulness is None or faithfulness < 0.5:
        return END  # type: ignore[return-value]

    # 3. Adversarial block (ai-guardrails.md Rule 13: fail closed)
    adversarial_pass_rate = state.get("adversarial_pass_rate")
    if adversarial_pass_rate is None or adversarial_pass_rate < 1.0:
        return END  # type: ignore[return-value]

    score = state.get("unified_score") or 0.0
    if score >= 0.85:
        return "deployer"
    if score >= 0.70:
        return "hitl"  # human approval required (SendGrid + Twilio — task F-8)
    return "observer"  # retry loop: observer → diagnoser → improver → ingestion


def _route_after_observer(state: GraphState) -> str:
    """Route from observer: diagnoser for analysis, or end if max retries reached."""
    retry_count = state.get("retry_count") or 0
    max_retries_val = state.get("max_retries")
    limit = 3 if max_retries_val is None else max_retries_val
    if retry_count >= limit:
        return END  # type: ignore[return-value]
    return "diagnoser"


def _route_after_improver(state: GraphState) -> str:
    """After improver generates a variant, loop back to ingestion for re-evaluation."""
    return "ingestion"


def _route_after_deployer(state: GraphState) -> str:
    """After deployer: observer continues monitoring on rollback, END on success/failure."""
    if state.get("deploy_status") == "rolled_back":
        return "observer"
    return END  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────────────
# Public aliases — used by tests and external callers
# ──────────────────────────────────────────────────────────────────────────────

route_after_evaluation = _route_after_evaluator
route_after_diagnosis = _route_after_observer
route_after_deployment = _route_after_deployer


# ──────────────────────────────────────────────────────────────────────────────
# Graph assembly
# ──────────────────────────────────────────────────────────────────────────────


def build_autorag_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph:
    """Assemble and compile the AutoRAG 9-agent LangGraph."""
    graph = StateGraph(GraphState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("query_rewriter", query_rewriter_node)
    graph.add_node("builder", builder_node)
    graph.add_node("compressor", compressor_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("observer", observer_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("improver", improver_node)
    graph.add_node("deployer", deployer_node)
    graph.add_node("hitl", _hitl_approval_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.set_entry_point("ingestion")

    # ── Linear edges (happy path) ──────────────────────────────────────────────
    graph.add_edge("ingestion", "query_rewriter")
    graph.add_edge("query_rewriter", "builder")
    graph.add_edge("builder", "compressor")
    graph.add_edge("compressor", "evaluator")

    # ── Conditional edges (score-driven routing) ───────────────────────────────
    graph.add_conditional_edges(
        "evaluator",
        _route_after_evaluator,
        {
            "deployer": "deployer",
            "hitl": "hitl",
            "observer": "observer",
            END: END,
        },
    )

    graph.add_edge("hitl", "deployer")

    graph.add_conditional_edges(
        "observer",
        _route_after_observer,
        {
            "diagnoser": "diagnoser",
            END: END,
        },
    )

    graph.add_edge("diagnoser", "improver")

    graph.add_conditional_edges(
        "improver",
        _route_after_improver,
        {
            "ingestion": "ingestion",
        },
    )

    graph.add_conditional_edges(
        "deployer",
        _route_after_deployer,
        {
            "observer": "observer",
            END: END,
        },
    )

    return graph.compile(checkpointer=checkpointer)


# ──────────────────────────────────────────────────────────────────────────────
# Async factory — used in FastAPI lifespan (app/main.py)
# ──────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def create_workflow_with_checkpointer() -> (
    AsyncGenerator[CompiledStateGraph, None]
):
    """Context manager that wires AsyncPostgresSaver and yields a compiled graph.

    Usage in FastAPI lifespan:
        async with create_workflow_with_checkpointer() as workflow:
            app.state.workflow = workflow
            yield

    In local/testing environments (no DATABASE_URL) falls back to MemorySaver
    so the graph still runs without a database connection.

    Every graph invocation must pass:
        config={"configurable": {"thread_id": pipeline_id, "x_trace_id": x_trace_id}}
    """
    # Local env: always use MemorySaver — psycopg binary wheels not guaranteed on all platforms
    if settings.environment == "local":
        logger.warning(
            "Local environment detected — using MemorySaver (no persistence). "
            "Set ENVIRONMENT=development or higher to enable PostgreSQL checkpointing."
        )
        yield build_autorag_graph(checkpointer=MemorySaver())
        return

    # Use DATABASE_URL (set by docker-compose for local) or fall back to SUPABASE_DB_URL
    db_url = settings.database_url if settings.is_local else settings.supabase_db_url
    if not db_url:
        logger.warning(
            "DATABASE_URL not set — using MemorySaver (no persistence). "
            "This is only acceptable in local/testing environments."
        )
        yield build_autorag_graph(checkpointer=MemorySaver())
        return

    # Convert SQLAlchemy URL format to psycopg format (LangGraph requirement)
    # postgresql+asyncpg://... → postgresql://...
    db_url_psycopg = db_url.replace("postgresql+asyncpg://", "postgresql://")

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: PLC0415

    async with AsyncPostgresSaver.from_conn_string(db_url_psycopg) as checkpointer:
        await checkpointer.setup()
        logger.info("AsyncPostgresSaver ready — checkpointing to PostgreSQL")
        yield build_autorag_graph(checkpointer=checkpointer)


autorag_workflow = build_autorag_graph()
