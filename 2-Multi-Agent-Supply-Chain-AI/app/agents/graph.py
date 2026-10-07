"""The supervisor graph (LangGraph).

input_guard ─(blocked)→ finalize
     │
  classify ─(out of scope)→ synthesize
     │
   plan ─→ dispatch: Send(stage agents in parallel) ─→ stage_join ─(more stages)→ dispatch
                                                         │(done)
                                                      synthesize (streams tokens) → validate
                                                         │
                                         (PO value > threshold) human_approval (interrupt) → finalize
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessageChunk
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send, interrupt

from app.agents import report as reports
from app.agents.intents import NEEDS_SKU, PLANS, Classification, extract_skus, keyword_route
from app.agents.prompts import classifier_prompt, permissions_for, synthesizer_prompt
from app.agents.specialist import run_specialist
from app.agents.state import SupplyChainState
from app.core.errors import ProviderFailure
from app.core.llm import with_fallbacks
from app.core.metrics import AGENT_LATENCY
from app.core.rbac import Role, User
from app.guardrails.pipeline import Guardrails
from app.tools.base import ToolContext
from app.tools.domain import build_tools

logger = logging.getLogger(__name__)

SPECIALISTS = ["demand", "inventory", "supplier", "logistics", "rag", "research"]
RUNNING_MESSAGE = {
    "demand": "Analyzing demand…",
    "inventory": "Checking inventory…",
    "supplier": "Comparing suppliers…",
    "logistics": "Checking shipments…",
    "rag": "Searching policies and contracts…",
    "research": "Researching external sources…",
}


@dataclass
class GraphDeps:
    """Everything the graph needs, injected by the container (tests pass fakes)."""

    services: Any  # Services: db, analytics, knowledge, web, guardrails, settings, activity, approvals
    agent_models: Callable[[], list[Any]]
    answer_models: Callable[[], list[Any]]
    guardrails: Guardrails
    approval_threshold: float
    approval_ttl_hours: int
    max_tool_iterations: int
    node_timeout_seconds: float
    record_event: Callable[..., Awaitable[None]]


def _user(state: dict[str, Any]) -> User:
    u = state["user"]
    return User(id=u["id"], email=u.get("email", ""), name=u.get("name", ""), role=Role.parse(u.get("role")))


def _emit(step: str, status: str, message: str, duration_ms: int | None = None) -> None:
    writer = get_stream_writer()
    event: dict[str, Any] = {"type": "step", "step": step, "status": status, "message": message}
    if duration_ms is not None:
        event["durationMs"] = duration_ms
    writer(event)


def build_graph(deps: GraphDeps, checkpointer: Any = None) -> Any:  # noqa: PLR0915 - graph wiring reads best in one place
    g = deps.guardrails

    # ------------------------------------------------------------------ input guardrails
    async def input_guard(state: SupplyChainState) -> dict[str, Any]:
        _emit("guard", "running", "Checking input guardrails…")
        started = time.perf_counter()
        result = g.check_input(state["user_query"])
        ms = round((time.perf_counter() - started) * 1000)
        if result.blocked:
            _emit("guard", "failed", "Request blocked by guardrails", ms)
            await deps.record_event(
                state,
                agent="supervisor",
                kind="error",
                severity="warning",
                message=f"Input blocked by guardrails ({', '.join(result.reasons[:2])})",
            )
            return {"blocked": True, "block_message": result.message or "", "intent": "blocked", "plan": []}
        msg = "Sensitive data redacted" if result.action == "redact" else "No injection or sensitive data detected"
        _emit("guard", "completed", msg, ms)
        return {"user_query": result.text, "blocked": False}

    # ------------------------------------------------------------------ intent classifier (structured output)
    async def classify(state: SupplyChainState) -> dict[str, Any]:
        _emit("classifier", "running", "Understanding request…")
        started = time.perf_counter()
        history = "\n".join(f"{h['role']}: {h['content'][:300]}" for h in state.get("history", [])[-6:]) or "(none)"
        try:
            llm = with_fallbacks(deps.agent_models(), lambda m: m.with_structured_output(Classification, method="function_calling"))
            result: Classification = await llm.ainvoke(classifier_prompt().format_messages(history=history, question=state["user_query"]))
            if result.confidence < 0.4:
                result = keyword_route(state["user_query"])
        except (ProviderFailure, ValueError) as exc:
            logger.warning("classifier unavailable — keyword router", extra={"error": type(exc).__name__})
            result = keyword_route(state["user_query"])
        skus = list(dict.fromkeys([s.upper() for s in result.skus] + extract_skus(state["user_query"])))
        intent = result.intent
        if intent == "out_of_scope" and g.in_scope(state["user_query"]):
            intent = keyword_route(state["user_query"]).intent  # policy layer: don't refuse clear supply-chain questions
        ms = round((time.perf_counter() - started) * 1000)
        _emit("classifier", "completed", f"Intent: {intent.replace('_', ' ')}" + (f" · {', '.join(skus)}" if skus else ""), ms)
        return {
            "intent": intent,
            "skus": skus,
            "standalone_question": result.standalone_question or state["user_query"],
            "classifier_confidence": result.confidence,
        }

    # ------------------------------------------------------------------ supervisor: plan
    async def plan(state: SupplyChainState) -> dict[str, Any]:
        _emit("supervisor", "running", "Planning workflow…")
        intent = state["intent"]
        stages = [list(s) for s in PLANS.get(intent, [])]
        skus = state.get("skus", [])
        if intent in NEEDS_SKU and not skus:
            # No SKU given: focus on the most critical product rather than guessing.
            top = await deps.services.analytics.at_risk(1)
            if top:
                skus = [top[0].row.sku]
        if intent == "research" and deps.services.web is None:
            stages = [["rag"]]
        n = sum(len(s) for s in stages)
        msg = (
            f"Routed to {n} agents in {len(stages)} stage{'s' if len(stages) != 1 else ''}" if stages else "Out of scope — no agents needed"
        )
        _emit("supervisor", "completed", msg)
        writer = get_stream_writer()
        writer({"type": "plan", "intent": intent, "agents": [a for s in stages for a in s], "stages": stages})
        await deps.record_event(
            state,
            agent="supervisor",
            kind="workflow",
            severity="info",
            message=f"Supervisor started workflow: {intent.replace('_', ' ')}" + (f" for {skus[0]}" if skus else ""),
            sku=skus[0] if skus else None,
        )
        return {"plan": stages, "stage": 0, "skus": skus}

    def dispatch(state: SupplyChainState) -> list[Send] | str:
        stages = state.get("plan", [])
        stage = state.get("stage", 0)
        if stage >= len(stages):
            return "synthesize"
        return [Send(f"{agent}_agent", state) for agent in stages[stage]]

    async def stage_join(state: SupplyChainState) -> dict[str, Any]:
        stage = state.get("stage", 0) + 1
        stages = state.get("plan", [])
        # Data-aware conditional skip: no supplier comparison when nothing needs reordering.
        if stage < len(stages) and "supplier" in stages[stage] and state.get("intent") != "supplier_selection":
            inv = state.get("inventory_data") or {}
            if inv.get("sku") and not inv.get("reorder_qty"):
                stages = [list(s) for s in stages]
                stages[stage] = [a for a in stages[stage] if a != "supplier"]
                _emit("supplier", "skipped", "Skipped — no reorder needed")
                if not stages[stage]:
                    stages.pop(stage)
                return {"stage": stage, "plan": stages}
        return {"stage": stage}

    # ------------------------------------------------------------------ specialists
    def specialist_node(agent: str) -> Callable[[SupplyChainState], Awaitable[dict[str, Any]]]:
        async def node(state: SupplyChainState) -> dict[str, Any]:
            _emit(agent, "running", RUNNING_MESSAGE[agent])
            user = _user(state)
            ctx = ToolContext(user=user, services=deps.services, run_id=state["run_id"])
            tools = build_tools(ctx)
            try:
                models = deps.agent_models()
            except ProviderFailure:
                models = []
            try:
                import asyncio

                outcome = await asyncio.wait_for(
                    run_specialist(
                        agent=agent,
                        state=dict(state),
                        user=user,
                        tools=tools,
                        models=models,
                        ctx=ctx,
                        max_iterations=deps.max_tool_iterations,
                    ),
                    timeout=deps.node_timeout_seconds,
                )
            except TimeoutError:
                AGENT_LATENCY.labels(agent, "timeout").observe(deps.node_timeout_seconds)
                _emit(agent, "failed", "Timed out")
                await deps.record_event(
                    state, agent=agent, kind="error", severity="warning", message=f"{agent.title()} Agent timed out", outcome="failed"
                )
                return {"errors": [{"agent": agent, "error": "timeout"}]}
            update, summary = _extract(agent, outcome.results, state)
            AGENT_LATENCY.labels(agent, "ok" if not outcome.errors else "partial").observe(outcome.duration_ms / 1000)
            failed = not outcome.results and bool(outcome.errors)
            _emit(agent, "failed" if failed else "completed", summary, outcome.duration_ms)
            await deps.record_event(
                state,
                agent=agent,
                kind="analysis",
                severity="warning" if failed else "success",
                message=f"{_label(agent)}: {summary}",
                duration_ms=outcome.duration_ms,
                outcome="failed" if failed else "success",
                sku=(state.get("skus") or [None])[0],
            )
            notes = {agent: outcome.notes} if outcome.notes else {}
            return {
                **update,
                "agent_notes": notes,
                "errors": outcome.errors,
                "tool_results": [{"agent": agent, **c} for c in outcome.calls],
            }

        node.__name__ = f"{agent}_agent"
        return node

    # ------------------------------------------------------------------ synthesizer (streams tokens)
    async def synthesize(state: SupplyChainState) -> dict[str, Any]:
        _emit("synthesizer", "running", "Preparing recommendation…")
        started = time.perf_counter()
        report = reports.build_report(dict(state), approval_threshold=deps.approval_threshold, approval_ttl_hours=deps.approval_ttl_hours)
        if state.get("blocked") or state.get("intent") == "out_of_scope":
            _emit("synthesizer", "completed", "Response prepared")
            return {"report": report, "recommendation": report["summary"], "approval": None}
        facts = reports.facts_for(dict(state))
        docs = state.get("retrieved_documents", [])
        passages = (
            "\n\n".join(g.fence(f"PASSAGE {d['n']}", f"[{d['n']}] ({d['source']}, {d['location']})\n{d['text']}") for d in docs) or "(none)"
        )
        notes = "\n".join(f"- {a}: {n}" for a, n in state.get("agent_notes", {}).items()) or "(none)"
        messages = synthesizer_prompt().format_messages(
            permissions=permissions_for(_user(state).role),
            question=state.get("standalone_question") or state["user_query"],
            facts=json.dumps(facts, default=str)[:6000],
            notes=notes[:3000],
            passages=passages[:8000],
        )
        text = ""
        try:
            llm = with_fallbacks(deps.answer_models())
            async for chunk in llm.astream(messages):  # tokens flow to the client via stream_mode="messages"
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    text += str(chunk.content)
        except ProviderFailure as exc:
            logger.warning("synthesizer unavailable — deterministic summary", extra={"error": exc.code})
            text = reports.fallback_summary(report, dict(state))
            get_stream_writer()({"type": "token", "text": text})
        report["summary"] = text.strip() or reports.fallback_summary(report, dict(state))
        _emit("synthesizer", "completed", "Report drafted from tool evidence", round((time.perf_counter() - started) * 1000))
        return {"report": report, "recommendation": report["summary"], "approval": report.get("approval")}

    # ------------------------------------------------------------------ validator (output guardrails)
    async def validate(state: SupplyChainState) -> dict[str, Any]:
        _emit("validator", "running", "Validating against evidence…")
        report = dict(state["report"])
        if state.get("blocked") or state.get("intent") == "out_of_scope":
            _emit("validator", "completed", "Nothing to validate")
            return {}
        docs = state.get("retrieved_documents", [])
        result = g.check_output(
            report["summary"],
            passages=len(docs),
            evidence_text=reports.evidence_text(dict(state)),
            require_citations=state.get("intent") == "policy_question",
        )
        if result.blocked:
            report["summary"] = reports.fallback_summary(report, dict(state))
            report["guard"] = {"status": "flagged", "reasons": result.reasons}
            _emit("validator", "completed", "Narrative replaced with verified summary")
        elif result.action == "flag":
            report["summary"] = result.text
            report["guard"] = {"status": "flagged", "reasons": result.reasons}
            _emit("validator", "completed", "Flagged: " + ", ".join(r.split(":")[0] for r in result.reasons))
        else:
            report["summary"] = result.text
            _emit("validator", "completed", "All figures and citations verified")
        return {"report": report, "recommendation": report["summary"]}

    def after_validate(state: SupplyChainState) -> str:
        return "human_approval" if state.get("approval") else "finalize"

    # ------------------------------------------------------------------ human-in-the-loop
    async def human_approval(state: SupplyChainState) -> dict[str, Any]:
        approval = state.get("approval")
        if not approval:
            return {}
        # Idempotent: a resumed run re-executes this node; the approval row is keyed by thread.
        await deps.services.approvals.ensure_pending(approval, thread_id=state["run_id"], requested_by=state["user"]["id"])
        _emit("approval", "running", "Awaiting approver decision")
        get_stream_writer()({"type": "approval_required", "approval": approval})
        decision = interrupt({"approval_id": approval["id"], "sku": approval["sku"], "value": approval["value"]})
        status = decision.get("decision", "rejected")
        report = dict(state["report"])
        report["approval"] = {**approval, "status": status}
        return {"approval_decision": decision, "approval": report["approval"], "report": report}

    async def finalize(state: SupplyChainState) -> dict[str, Any]:
        return {}

    # ------------------------------------------------------------------ wiring
    graph = StateGraph(SupplyChainState)
    retry = RetryPolicy(max_attempts=2, retry_on=(ConnectionError, TimeoutError))
    graph.add_node("input_guard", input_guard)
    graph.add_node("classify", classify, retry_policy=retry)
    graph.add_node("plan", plan)
    graph.add_node("stage_join", stage_join)
    for agent in SPECIALISTS:
        graph.add_node(f"{agent}_agent", specialist_node(agent), retry_policy=retry)
        graph.add_edge(f"{agent}_agent", "stage_join")
    graph.add_node("synthesize", synthesize)
    graph.add_node("validate", validate)
    graph.add_node("human_approval", human_approval)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges("input_guard", lambda s: "synthesize" if s.get("blocked") else "classify", ["synthesize", "classify"])
    graph.add_edge("classify", "plan")
    targets = [f"{a}_agent" for a in SPECIALISTS] + ["synthesize"]
    graph.add_conditional_edges("plan", dispatch, targets)
    graph.add_conditional_edges("stage_join", dispatch, targets)
    graph.add_edge("synthesize", "validate")
    graph.add_conditional_edges("validate", after_validate, ["human_approval", "finalize"])
    graph.add_edge("human_approval", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def _label(agent: str) -> str:
    return {
        "rag": "Knowledge Agent",
        "demand": "Demand Agent",
        "inventory": "Inventory Agent",
        "supplier": "Supplier Agent",
        "logistics": "Logistics Agent",
        "research": "Research Agent",
    }[agent]


def _extract(agent: str, results: dict[str, Any], state: SupplyChainState) -> tuple[dict[str, Any], str]:
    """Map tool results to the agent's state key and a one-line status for the UI."""
    if agent == "demand":
        fc = results.get("get_demand_forecast")
        return (
            ({"demand_forecast": fc}, f"Forecast {fc['total']:,} units / {fc['horizon_days']} days")
            if fc
            else ({}, "No forecast available")
        )
    if agent == "inventory":
        inv = dict(results.get("get_inventory") or {})
        inv.update(results.get("calculate_reorder_quantity") or {})
        if risks := results.get("get_stockout_risks"):
            inv["at_risk"] = risks["items"]
            return {"inventory_data": inv}, f"{risks['count']} products at risk"
        if not inv:
            return {"inventory_data": {"not_found": True}}, "SKU not found"
        return {"inventory_data": inv}, f"{inv.get('days_of_cover')} days of cover · {inv.get('risk')} risk"
    if agent == "supplier":
        rec = results.get("recommend_supplier")
        if not rec or not rec.get("recommended"):
            return {}, "No supplier recommendation"
        return {"supplier_data": rec}, f"{len(rec['ranked'])} compared · {rec['recommended']['name']}"
    if agent == "logistics":
        ships = (results.get("get_shipments") or {}).get("shipments", [])
        delayed = [s for s in ships if s["status"] == "delayed" or s["delay_days"] > 0]
        return {
            "logistics_data": {"shipments": delayed if state.get("intent") == "shipment_status" else ships, "delayed_count": len(delayed)}
        }, f"{len(delayed)} delayed shipments reviewed"
    if agent in {"rag", "research"}:
        passages = (results.get("search_knowledge_base") or {}).get("passages", [])
        docs = [{"n": p["n"], "source": p["source"], "location": p["location"], "text": p["text"]} for p in passages]
        update: dict[str, Any] = {"retrieved_documents": docs}
        if agent == "research" and (web := results.get("search_web")):
            update["research_data"] = {"web_sources": [{"title": r["title"], "url": r["url"]} for r in web.get("results", [])]}
        return update, f"{len(docs)} relevant passages retrieved"
    return {}, "Done"
