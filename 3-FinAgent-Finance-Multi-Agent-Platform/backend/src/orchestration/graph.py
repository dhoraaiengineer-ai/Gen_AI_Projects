"""Supervisor graph (LangGraph).

input_guard → classify → plan → [fan-out stage with Send → run_agent ×N → stage_join]* →
synthesize → validate → report

* Agents are reached only through **A2A envelopes** (``A2AClient``); each stage's agents run in
  parallel (``Send``), stages run in dependency order, later stages see earlier results.
* ``synthesize`` asks the answer-chain LLM for a short narrative over agent highlights (streamed
  as ``token`` events); ``validate`` rejects narratives with numbers that are not in the facts.
* Progress is emitted on the ``custom`` stream: step, plan, agent_start, agent_end, token, report.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from src.a2a.client import A2AClient, A2AError
from src.a2a.messages import A2AContext
from src.agents.report.agent import build_report
from src.core.errors import AppError
from src.core.tokens import estimate_tokens, fit_lines
from src.guardrails.checks import EXECUTION_NOTE, check_input, check_output
from src.orchestration.routing import (
    AGENT_TASKS,
    INTENT_PERMISSIONS,
    NOT_YET_AVAILABLE,
    PLANS,
    Classification,
    PortfolioRef,
    Router,
)
from src.orchestration.state import FinanceState
from src.security.audit import AuditEvent, AuditService
from src.security.rbac import has_permission

logger = logging.getLogger(__name__)

NarrativeModel = Callable[[], Any]  # returns a runnable supporting .astream(messages)
PortfolioLister = Callable[[FinanceState], Awaitable[list[PortfolioRef]]]


class ApprovalStore(Protocol):
    async def create(
        self,
        *,
        request_id: str,
        thread_id: str,
        portfolio_code: str | None,
        proposal: dict[str, Any],
        reasons: list[str],
        requested_by: str | None,
    ) -> dict[str, Any]: ...


PORTFOLIO_INTENTS = {
    "portfolio_risk",
    "risk_increase_explanation",
    "executive_report",
    "portfolio_overview",
    "compliance_check",
    "rebalance",
}
_NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?(?:%|bn|M|k)?")

SYNTH_SYSTEM = (
    "You are FinAgent, a decision-support assistant for an asset manager. Answer the question "
    "in at most 150 words using ONLY the facts provided. Copy every number exactly as written in "
    "the facts (same digits, decimals and units); do not compute or round anything. Start with one "
    "headline "
    "sentence, then 3-5 short bullet points. If approval is required, say so. Never give "
    "personalised investment advice or promise returns."
)


@dataclass
class GraphDeps:
    a2a: A2AClient
    router: Router
    list_portfolios: PortfolioLister
    narrative_model: NarrativeModel | None = None  # None = deterministic narrative
    narrative_max_input_tokens: int = 2_500  # ADR-029
    narrative_min_output_tokens: int = 40
    max_input_chars: int = 4_000
    audit: AuditService | None = None
    approvals: ApprovalStore | None = None  # None = approvals not persisted (offline tests)
    checkpointer: Any = None  # LangGraph saver; required to pause for a human decision


def _emit(event: str, **data: Any) -> None:
    try:
        writer = get_stream_writer()
    except RuntimeError:  # not running under a streaming call
        return
    writer({"event": event, "ts": time.time(), **data})


def _context(state: FinanceState, upstream: list[str]) -> A2AContext:
    return A2AContext(
        request_id=state["request_id"],
        trace_id=state["trace_id"],
        tenant_id=state["tenant_id"],
        role=state["role"],
        user_id=state.get("user_id"),
        upstream=upstream,
    )


def deterministic_narrative(state: FinanceState) -> str:
    results = state.get("agent_results", {})
    lines = [
        h
        for r in results.values()
        for h in r.get("highlights", [])
        if not h.startswith("Decision support only")
    ]
    return "\n".join(f"- {line}" for line in lines[:8])


def ungrounded_numbers(narrative: str, facts_text: str) -> list[str]:
    """Numbers in the narrative that do not appear verbatim in the facts."""
    found = []
    for token in _NUMBER_RE.findall(narrative):
        clean = token.lstrip("+")
        digits = re.sub(r"[^\d]", "", clean)
        if len(digits) <= 1:  # list markers, single digits ("3 breaches")
            continue
        if clean not in facts_text:
            found.append(clean)
    return found


def build_graph(deps: GraphDeps) -> Any:
    async def audit(
        state: FinanceState, action: str, decision: str, reason: str, **details: Any
    ) -> None:
        if deps.audit is not None:
            await deps.audit.record(
                AuditEvent(
                    action=action,
                    decision=decision,
                    reason=reason,
                    request_id=state.get("request_id"),
                    trace_id=state.get("trace_id"),
                    user_id=state.get("user_id"),
                    user_role=state.get("role"),
                    details=details,
                )
            )

    async def input_guard(state: FinanceState) -> dict[str, Any]:
        _emit("step", step="input_guard")
        verdict = check_input(state.get("question") or "", deps.max_input_chars)
        if not verdict.allowed:
            await audit(state, "guardrail.input", "block", verdict.reason or "blocked")
            _emit("guard", decision="block", reason=verdict.reason)
            return {
                "blocked": True,
                "question": "",  # never keep blocked text (may hold a secret)
                "guard_reason": verdict.reason,
                "guard_message": verdict.message,
                "errors": [f"input blocked: {verdict.reason}"],
            }
        notes = [EXECUTION_NOTE] if "execution_request" in verdict.flags else []
        if verdict.flags:
            await audit(state, "guardrail.input", "flag", ",".join(verdict.flags))
        return {
            "blocked": False,
            "question": verdict.question,  # PII-redacted
            "guard_flags": verdict.flags,
            "assumptions": notes,
        }

    async def classify(state: FinanceState) -> dict[str, Any]:
        _emit("step", step="classify")
        portfolios = await deps.list_portfolios(state)
        forced = state.get("forced") or {}
        if forced.get("intent"):  # structured API call: intent known, no classification needed
            result = Classification(
                intent=forced["intent"],
                portfolio_id=forced.get("portfolio_id"),
                tickers=list(forced.get("tickers") or []),
                standalone_question=state["question"],
                confidence=1.0,
                method="api",
            )
        else:
            result = await deps.router.classify(state["question"], portfolios)
        assumptions: list[str] = []
        portfolio_id = result.portfolio_id
        tickers = result.tickers
        previous = (state.get("history") or [])[-1:]
        if previous and not portfolio_id and not tickers:
            # Follow-up ("and its VaR?"): keep what the conversation was about.
            last = previous[0]
            if result.intent in PORTFOLIO_INTENTS and last.get("portfolio"):
                portfolio_id = str(last["portfolio"])
                assumptions.append(
                    f"Follow-up question: kept portfolio {portfolio_id} from the conversation."
                )
            elif result.intent not in PORTFOLIO_INTENTS and last.get("tickers"):
                tickers = [str(t) for t in last["tickers"]]
                assumptions.append(
                    f"Follow-up question: kept {', '.join(tickers)} from the conversation."
                )
        if result.intent in PORTFOLIO_INTENTS and not portfolio_id and portfolios:
            portfolio_id = portfolios[0].code
            assumptions.append(
                "No portfolio named in the question; "
                f"analysed {portfolios[0].name} ({portfolio_id})."
            )
        _emit(
            "classification",
            intent=result.intent,
            method=result.method,
            portfolio=portfolio_id,
            confidence=result.confidence,
        )
        return {
            "intent": result.intent,
            "portfolio_id": portfolio_id,
            "tickers": tickers,
            "classification": result.model_dump(),
            "assumptions": assumptions,
        }

    async def plan(state: FinanceState) -> dict[str, Any]:
        intent = state["intent"]
        needed = INTENT_PERMISSIONS.get(intent, "agents:run")
        if not has_permission(state.get("role", ""), needed):
            await audit(state, "rbac.intent", "deny", f"{intent} needs {needed}")
            message = (
                f"Your role ({state.get('role')}) is not permitted to run this analysis "
                f"({intent.replace('_', ' ')}); it needs the '{needed}' permission."
            )
            _emit("guard", decision="deny", reason="permission")
            return {
                "plan": [],
                "stage_index": 0,
                "blocked": True,
                "guard_reason": "permission",
                "guard_message": message,
            }
        stages = PLANS.get(intent, [])
        notes = [NOT_YET_AVAILABLE[intent]] if intent in NOT_YET_AVAILABLE else []
        _emit("plan", intent=intent, stages=stages)
        return {"plan": stages, "stage_index": 0, "assumptions": notes}

    def fan_out(state: FinanceState) -> list[Send] | str:
        if state.get("blocked"):
            return "report"
        index, stages = state.get("stage_index", 0), state.get("plan", [])
        if index >= len(stages):
            return "synthesize"
        return [Send("run_agent", {**state, "agent": name}) for name in stages[index]]

    async def run_agent(state: FinanceState) -> dict[str, Any]:
        agent = state["agent"]
        previous = state.get("agent_results", {})
        _emit("agent_start", agent=agent)
        payload = {
            "task": AGENT_TASKS[agent],
            "question": state["question"],
            "portfolio_id": state.get("portfolio_id"),
            "tickers": state.get("tickers", []),
            "upstream": {a: r.get("highlights", []) for a, r in previous.items()},
            "upstream_data": {a: r.get("extra", {}) for a, r in previous.items()},
        }
        if state.get("intent") == "rebalance" and agent == "portfolio":
            payload["task"] = "propose_rebalance"
        try:
            reply = await deps.a2a.send(
                source="supervisor",
                target=agent,
                task=str(payload["task"]),
                payload=payload,
                context=_context(state, list(previous)),
            )
            result = reply.payload
        except A2AError as exc:
            logger.warning("agent failed", extra={"agent": agent, "code": exc.code})
            result = {
                "agent": agent,
                "task": payload["task"],
                "status": "failed",
                "highlights": [],
                "errors": [f"{exc.code}"],
                "confidence": 0.0,
                "tool_calls": [],
                "evidence": [],
                "extra": {},
            }
        _emit(
            "agent_end",
            agent=agent,
            status=result.get("status"),
            confidence=result.get("confidence"),
            tools=[c["tool"] for c in result.get("tool_calls", [])],
            durationMs=result.get("duration_ms"),
        )
        return {"agent_results": {agent: result}}

    async def stage_join(state: FinanceState) -> dict[str, Any]:
        return {"stage_index": state.get("stage_index", 0) + 1}

    async def synthesize(state: FinanceState) -> dict[str, Any]:
        _emit("step", step="synthesize")
        results = state.get("agent_results", {})
        if not results:
            return {"narrative": None, "narrative_source": "none"}
        research = results.get("research", {}).get("extra", {})
        if state.get("intent") == "knowledge_question" and research.get("answer"):
            # Already a validated, cited RAG answer: no second LLM pass.
            return {"narrative": research["answer"], "narrative_source": "rag"}
        if deps.narrative_model is None:
            return {
                "narrative": deterministic_narrative(state),
                "narrative_source": "deterministic",
            }
        lines = [f"[{a}] {h}" for a, r in results.items() for h in r.get("highlights", [])]
        overhead = estimate_tokens(SYNTH_SYSTEM) + estimate_tokens(state["question"]) + 20
        facts = "\n".join(fit_lines(lines, max(200, deps.narrative_max_input_tokens - overhead)))
        messages = [
            SystemMessage(SYNTH_SYSTEM),
            HumanMessage(f"Question: {state['question']}\n\nFacts:\n{facts}"),
        ]
        chunks: list[str] = []
        try:
            model = deps.narrative_model()
            async for chunk in model.astream(messages):
                text = str(getattr(chunk, "content", "") or "")
                if text:
                    chunks.append(text)
                    _emit("token", text=text)
        except AppError as exc:
            logger.warning(
                "narrative model failed; deterministic narrative", extra={"error": exc.code}
            )
            return {
                "narrative": deterministic_narrative(state),
                "narrative_source": "deterministic",
                "errors": [f"narrative: {exc.code}"],
            }
        narrative = "".join(chunks).strip()
        if estimate_tokens(narrative) < deps.narrative_min_output_tokens:
            logger.warning("narrative below minimum length; deterministic narrative")
            return {
                "narrative": deterministic_narrative(state),
                "narrative_source": "deterministic",
                "errors": ["narrative: below minimum output"],
            }
        return {"narrative": narrative, "narrative_source": "llm"}

    async def validate(state: FinanceState) -> dict[str, Any]:
        _emit("step", step="validate")
        narrative = state.get("narrative") or ""
        if state.get("narrative_source") != "llm":
            return {"validation": {"ungrounded": [], "output": []}}
        facts_text = " ".join(
            h for r in state.get("agent_results", {}).values() for h in r.get("highlights", [])
        )
        redacted, flags = check_output(narrative)
        unsafe = [f for f in flags if not f.startswith("pii:")]
        bad = ungrounded_numbers(redacted, facts_text)
        if bad or unsafe:
            logger.warning(
                "narrative rejected", extra={"ungrounded": len(bad), "output_flags": unsafe}
            )
            if unsafe:
                await audit(state, "guardrail.output", "block", ",".join(unsafe))
            return {
                "validation": {"ungrounded": bad, "output": unsafe},
                "narrative": deterministic_narrative(state),
                "narrative_source": "deterministic",
            }
        return {"validation": {"ungrounded": [], "output": []}, "narrative": redacted}

    async def report(state: FinanceState) -> dict[str, Any]:
        built = build_report(dict(state))
        if not needs_approval(state, built):
            _emit("report", report=built)
        return {"report": built}

    def needs_approval(state: FinanceState, built: dict[str, Any]) -> bool:
        orders = state.get("agent_results", {}).get("portfolio", {}).get("extra", {})
        return bool(
            deps.approvals is not None
            and built.get("approval", {}).get("required")
            and orders.get("draftOrders")
        )

    async def request_approval(state: FinanceState) -> dict[str, Any]:
        """Persist a pending approval for the draft orders (idempotent on resume)."""
        assert deps.approvals is not None  # guarded by the edge  # noqa: S101
        built = dict(state["report"])
        extra = state["agent_results"]["portfolio"]["extra"]
        approval = await deps.approvals.create(
            request_id=state["request_id"],
            thread_id=state["request_id"],
            portfolio_code=state.get("portfolio_id"),
            proposal={"orders": extra["draftOrders"], "question": state.get("question", "")},
            reasons=list(built.get("approval", {}).get("reasons", [])),
            requested_by=state.get("user_id"),
        )
        built["approval"] = built["approval"] | {
            "approvalId": approval["approvalId"],
            "status": "pending",
            "expiresAt": approval["expiresAt"],
            "draftOrders": extra["draftOrders"],
        }
        await audit(state, "approval.request", "flag", "draft orders need approval",
                    approvalId=approval["approvalId"])  # fmt: skip
        _emit("approval", approval=built["approval"])
        _emit("report", report=built)
        return {"report": built}

    async def await_decision(state: FinanceState) -> dict[str, Any]:
        """Pause until a human decides.

        The runner validates and records the decision (segregation of duties, expiry, draft
        orders) *before* resuming, so a refused attempt never reaches the paused graph. The
        resume value is the recorded outcome: {"status", "decidedBy", "decidedAt", "note",
        "draftOrders"}.
        """
        pending = state["report"]["approval"]
        outcome = interrupt({"approvalId": pending["approvalId"], "reasons": pending["reasons"]})
        # The decision is audited by whoever records it (API presenter: the approver's identity),
        # not here — this state carries the requester's identity.
        built = dict(state["report"])
        built["approval"] = built["approval"] | {
            "status": outcome.get("status"),
            "decidedBy": outcome.get("decidedBy"),
            "decidedAt": outcome.get("decidedAt"),
            "createdDraftOrders": outcome.get("draftOrders", []),
        }
        _emit("report", report=built)
        return {"report": built}

    graph = StateGraph(FinanceState)
    graph.add_node("input_guard", input_guard)
    graph.add_node("classify", classify)
    graph.add_node("plan", plan)
    graph.add_node("run_agent", run_agent)
    graph.add_node("stage_join", stage_join)
    graph.add_node("synthesize", synthesize)
    graph.add_node("validate", validate)
    graph.add_node("report", report)
    graph.add_node("request_approval", request_approval)
    graph.add_node("await_decision", await_decision)
    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges(
        "input_guard",
        lambda s: "report" if s.get("blocked") else "classify",
        ["report", "classify"],
    )
    graph.add_edge("classify", "plan")
    graph.add_conditional_edges("plan", fan_out, ["run_agent", "synthesize", "report"])
    graph.add_edge("run_agent", "stage_join")
    graph.add_conditional_edges("stage_join", fan_out, ["run_agent", "synthesize", "report"])
    graph.add_edge("synthesize", "validate")
    graph.add_edge("validate", "report")
    graph.add_conditional_edges(
        "report",
        lambda s: "request_approval" if needs_approval(s, s["report"]) else END,
        ["request_approval", END],
    )
    graph.add_conditional_edges(
        "request_approval",
        lambda s: "await_decision" if deps.checkpointer is not None else END,
        ["await_decision", END],
    )
    graph.add_edge("await_decision", END)
    return graph.compile(checkpointer=deps.checkpointer)
