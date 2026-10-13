"""Supervisor runner: run the graph for one question, returning the report or streaming events."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from langgraph.types import Command

from src.core.context import new_request_id, new_trace_id
from src.core.errors import Conflict
from src.core.metrics import TTFE, TTFT
from src.core.tokens import start_meter, stop_meter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Caller:
    tenant_id: str
    role: str
    user_id: str | None = None


class ApprovalDecider(Protocol):
    async def decide(
        self, approval_id: str, *, approve: bool, decided_by: str | None, note: str | None
    ) -> dict[str, Any]: ...


class SupervisorRunner:
    def __init__(
        self, graph: Any, token_budget: int = 12_000, approvals: ApprovalDecider | None = None
    ) -> None:
        self.graph = graph
        self.token_budget = token_budget
        self.approvals = approvals

    @staticmethod
    def config(thread_id: str) -> dict[str, Any]:
        """Checkpoint thread = request id (approvals resume on the same thread)."""
        return {"configurable": {"thread_id": thread_id}}

    async def pending_approval(
        self, thread_id: str, tenant_id: str | None = None
    ) -> dict[str, Any] | None:
        """The approval a paused run is waiting for (None if not paused or another tenant's)."""
        snapshot = await self.graph.aget_state(self.config(thread_id))
        if "await_decision" not in (snapshot.next or ()):
            return None
        if tenant_id is not None and str(snapshot.values.get("tenant_id")) != str(tenant_id):
            return None
        approval: dict[str, Any] = snapshot.values["report"]["approval"]
        return approval

    async def resume(
        self, thread_id: str, decision: dict[str, Any], *, tenant_id: str | None = None
    ) -> dict[str, Any]:
        """Record the approver's decision, then continue the paused run with the outcome.

        ``decide`` raises (Forbidden: requester approving their own proposal; Conflict: already
        decided or expired) before the graph is touched, so the run stays paused for a valid
        approver. Decision: {"approve": bool, "decidedBy": str, "note": str | None}.
        """
        if self.approvals is None:
            raise Conflict("approvals are not configured")
        pending = await self.pending_approval(thread_id, tenant_id)
        if pending is None:
            raise Conflict("this run is not waiting for an approval")
        result = await self.approvals.decide(
            pending["approvalId"],
            approve=bool(decision.get("approve")),
            decided_by=decision.get("decidedBy"),
            note=decision.get("note"),
        )
        outcome = {
            "status": result["status"],
            "decidedBy": result.get("decidedBy"),
            "decidedAt": str(result["decidedAt"]) if result.get("decidedAt") else None,
            "note": decision.get("note"),
            "draftOrders": result.get("draftOrders", []),
        }
        state = await self.graph.ainvoke(Command(resume=outcome), self.config(thread_id))
        report: dict[str, Any] = state["report"]
        return report

    def _initial(
        self,
        question: str,
        caller: Caller,
        *,
        request_id: str | None,
        trace_id: str | None,
        history: list[dict[str, Any]] | None = None,
        forced: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "history": history or [],
            "forced": forced or {},
            "request_id": request_id or new_request_id(),
            "trace_id": trace_id or new_trace_id(),
            "tenant_id": caller.tenant_id,
            "role": caller.role,
            "user_id": caller.user_id,
            "question": question,
            "agent_results": {},
            "errors": [],
            "assumptions": [],
        }

    async def run(
        self,
        question: str,
        caller: Caller,
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        forced: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        meter, token = start_meter(self.token_budget)
        initial = self._initial(
            question,
            caller,
            request_id=request_id,
            trace_id=trace_id,
            history=history,
            forced=forced,
        )
        try:
            state = await self.graph.ainvoke(initial, self.config(initial["request_id"]))
        finally:
            stop_meter(token)
        report: dict[str, Any] = state["report"]
        report["durationMs"] = round((time.perf_counter() - started) * 1000)
        report["usage"] = meter.summary()
        return report

    async def stream(
        self,
        question: str,
        caller: Caller,
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield progress events (step, plan, agent_start/end, token, report, error, done)."""
        started = time.perf_counter()
        first_event = first_token = True
        initial = self._initial(
            question, caller, request_id=request_id, trace_id=trace_id, history=history
        )
        meter, token = start_meter(self.token_budget)
        yield {"event": "start", "requestId": initial["request_id"], "traceId": initial["trace_id"]}
        try:
            async for mode, chunk in self.graph.astream(
                initial, self.config(initial["request_id"]), stream_mode=["custom", "updates"]
            ):
                if mode != "custom":
                    continue
                if first_event:
                    TTFE.observe(time.perf_counter() - started)
                    first_event = False
                if chunk.get("event") == "token" and first_token:
                    TTFT.observe(time.perf_counter() - started)
                    first_token = False
                if chunk.get("event") == "report":
                    chunk["report"]["durationMs"] = round((time.perf_counter() - started) * 1000)
                    chunk["report"]["usage"] = meter.summary()
                yield chunk
        except Exception as exc:  # stream an error event instead of breaking the connection
            logger.exception("supervisor stream failed")
            yield {
                "event": "error",
                "message": "The analysis failed.",
                "code": type(exc).__name__,
                "requestId": initial["request_id"],
            }
        finally:
            stop_meter(token)
        yield {
            "event": "done",
            "durationMs": round((time.perf_counter() - started) * 1000),
            "usage": meter.summary(),
        }
