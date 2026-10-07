"""AgentService: runs the supervisor graph and turns LangGraph's stream into client events (SSE).

stream_mode = ["custom", "messages", "updates"]:
- custom   → step / plan / approval events written by nodes (get_stream_writer)
- messages → LLM token chunks; only the synthesizer's tokens are forwarded to the client
- updates  → used to detect the human-approval interrupt
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessageChunk
from langgraph.types import Command

from app.core.context import current_request_id
from app.core.errors import AppError
from app.core.metrics import STREAM_TTFE, STREAM_TTFT, WORKFLOWS
from app.core.rbac import User
from app.services.workflow import ApprovalService, MemoryService

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, graph: Any, memory: MemoryService, approvals: ApprovalService, recursion_limit: int) -> None:
        self._graph = graph
        self._memory = memory
        self._approvals = approvals
        self._recursion_limit = recursion_limit

    def _config(self, run_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": run_id},
            "recursion_limit": self._recursion_limit,
            "run_name": "supervisor",
            "tags": ["supply-chain-ai"],
        }

    async def stream(self, message: str, user: User, session_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        request_id = current_request_id()
        started = time.perf_counter()
        first_event = first_token = None
        intent = "unknown"
        yield {"type": "run_started", "runId": run_id, "requestId": request_id}
        history = await self._memory.recent(user.id, session_id)
        state_in = {
            "run_id": run_id,
            "request_id": request_id,
            "user_query": message,
            "history": history,
            "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role.value},
        }
        config = self._config(run_id)
        try:
            async for mode, chunk in self._graph.astream(state_in, config, stream_mode=["custom", "messages", "updates"]):
                if first_event is None:
                    first_event = time.perf_counter() - started
                    STREAM_TTFE.labels("chat").observe(first_event)
                if mode == "custom":
                    if chunk.get("type") == "plan":
                        intent = chunk.get("intent", intent)
                    if chunk.get("type") == "token" and first_token is None:
                        first_token = time.perf_counter() - started
                    yield chunk
                elif mode == "messages":
                    msg, meta = chunk
                    if meta.get("langgraph_node") == "synthesize" and isinstance(msg, AIMessageChunk) and msg.content:
                        if first_token is None:
                            first_token = time.perf_counter() - started
                            STREAM_TTFT.labels("chat").observe(first_token)
                        yield {"type": "token", "text": str(msg.content)}
                # updates mode: the interrupt surfaces here; the approval event was already emitted by the node.

            snapshot = await self._graph.aget_state(config)
            report = dict(snapshot.values.get("report") or {})
            report["latencyMs"] = round((time.perf_counter() - started) * 1000)
            report["requestId"] = request_id
            if snapshot.values.get("approval"):
                report["approval"] = snapshot.values["approval"]
            yield {"type": "report", "report": report}
            WORKFLOWS.labels(intent, "awaiting_approval" if snapshot.next else "completed").inc()
            await self._memory.append(
                user,
                session_id,
                message,
                report.get("summary", ""),
                {"runId": run_id, "intent": intent, "headline": report.get("headline")},
            )
        except AppError as exc:
            WORKFLOWS.labels(intent, "error").inc()
            logger.warning("workflow failed", extra={"run_id": run_id, "error": exc.code})
            yield {"type": "error", "message": exc.message, "requestId": request_id}
        except Exception:
            WORKFLOWS.labels(intent, "error").inc()
            logger.exception("workflow crashed", extra={"run_id": run_id})
            yield {"type": "error", "message": "The copilot couldn't complete this request.", "requestId": request_id}

    async def run(self, message: str, user: User, session_id: str | None = None) -> dict[str, Any]:
        """Non-streaming variant (POST /agents/run): collect the stream, return the final report and steps."""
        steps: list[dict[str, Any]] = []
        report: dict[str, Any] = {}
        async for ev in self.stream(message, user, session_id):
            if ev["type"] == "step":
                steps.append(ev)
            elif ev["type"] == "report":
                report = ev["report"]
            elif ev["type"] == "error":
                return {"error": ev}
        return {"report": report, "steps": steps}

    async def decide(self, approval_id: str, decision: str, user: User, comment: str | None) -> Any:
        """Record the decision atomically, then resume the paused graph from its checkpoint."""
        approval = await self._approvals.decide(approval_id, decision=decision, user=user, comment=comment)
        try:
            await self._graph.ainvoke(
                Command(resume={"decision": decision, "comment": comment, "decided_by": user.id}), self._config(approval.thread_id)
            )
        except Exception:
            # The decision is recorded and the PO draft exists; a missing checkpoint (e.g. expired) must not undo it.
            logger.exception("failed to resume workflow after approval", extra={"approval_id": approval_id})
        return approval
