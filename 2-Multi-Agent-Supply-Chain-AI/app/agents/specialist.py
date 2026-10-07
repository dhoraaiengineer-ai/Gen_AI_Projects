"""Specialist agent execution: a bounded LLM tool-calling loop with authorization, plus deterministic coverage.

1. The LLM (with fallback chain) chooses tools from the agent's role-filtered allow-list.
2. Every call is authorized against the registry; denied calls are returned to the model as errors.
3. After the loop, required tools the model skipped are executed directly, so outputs are always complete.
4. If every LLM provider is down, the agent degrades to the deterministic tool plan with a templated summary.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import StructuredTool

from app.agents.prompts import permissions_for, specialist_prompt
from app.core.errors import ProviderFailure
from app.core.llm import with_fallbacks
from app.core.rbac import User
from app.tools.base import ToolContext
from app.tools.registry import ToolDenied, authorize, tools_for

logger = logging.getLogger(__name__)


@dataclass
class SpecialistOutcome:
    agent: str
    notes: str
    results: dict[str, Any] = field(default_factory=dict)  # tool name → parsed data (last successful call)
    errors: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    llm_used: bool = True
    duration_ms: int = 0


def _parse(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"ok": False, "error": "bad_output"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "bad_output", "message": raw[:200]}


def required_calls(agent: str, intent: str, skus: list[str], state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """The minimum tool plan each agent must have executed for its output to be complete."""
    sku = skus[0] if skus else None
    if agent == "demand" and sku:
        return [("get_demand_forecast", {"sku": sku, "horizon_days": 30})]
    if agent == "inventory":
        if sku:
            return [("get_inventory", {"sku": sku}), ("calculate_reorder_quantity", {"sku": sku})]
        return [("get_stockout_risks", {"limit": 10})]
    if agent == "supplier" and sku:
        return [("recommend_supplier", {"sku": sku})]
    if agent == "logistics":
        if intent == "shipment_status" or not sku:
            return [("get_shipments", {"delayed_only": True, "limit": 15})]
        return [("get_shipments", {"sku": sku, "limit": 10})]
    if agent == "rag":
        query = state.get("standalone_question") or state.get("user_query", "")
        if intent == "full_recommendation" and sku:
            query = f"expedited orders approval threshold supplier lead time {sku}"
        return [("search_knowledge_base", {"query": query[:480]})]
    if agent == "research":
        return [("search_knowledge_base", {"query": (state.get("standalone_question") or state.get("user_query", ""))[:480]})]
    return []


def _context_lines(agent: str, state: dict[str, Any]) -> str:
    """Share upstream results with dependent agents (e.g. inventory sees the demand forecast)."""
    lines = []
    if agent in {"inventory", "supplier", "logistics"} and state.get("demand_forecast"):
        fc = state["demand_forecast"]
        lines.append(f"- Demand forecast (30d): {fc.get('total')} units, trend {fc.get('trend', {}).get('direction')}")
    if agent in {"supplier", "logistics"} and state.get("inventory_data"):
        inv = state["inventory_data"]
        lines.append(
            f"- Inventory: {inv.get('available')} available, {inv.get('days_of_cover')} days of cover, risk {inv.get('risk')}, reorder {inv.get('reorder_qty')}"  # noqa: E501
        )
    return "\n".join(lines) or "- (no upstream results)"


async def run_specialist(
    *,
    agent: str,
    state: dict[str, Any],
    user: User,
    tools: dict[str, StructuredTool],
    models: list[Any],
    ctx: ToolContext,
    max_iterations: int,
) -> SpecialistOutcome:
    started = time.perf_counter()
    intent = state.get("intent", "")
    skus = state.get("skus", [])
    allowed = [t for t in tools_for(agent, user) if t in tools]
    outcome = SpecialistOutcome(agent=agent, notes="")

    async def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
        authorize(name, agent, user)
        parsed = _parse(await tools[name].ainvoke(args))
        if parsed.get("ok"):
            outcome.results[name] = parsed["data"]
        else:
            outcome.errors.append({"agent": agent, "tool": name, "error": parsed.get("error"), "message": parsed.get("message")})
        return parsed

    # 1) LLM-driven tool loop (bounded)
    if allowed and models:
        prompt = specialist_prompt(agent)
        messages: list[BaseMessage] = prompt.format_messages(
            permissions=permissions_for(user.role),
            question=state.get("standalone_question") or state.get("user_query", ""),
            intent=intent,
            skus=", ".join(skus) or "none",
            context=_context_lines(agent, state),
            max_iterations=max_iterations,
        )
        llm = with_fallbacks(models, lambda m: m.bind_tools([tools[n] for n in allowed]))
        try:
            for _ in range(max_iterations):
                ai: AIMessage = await llm.ainvoke(messages)
                messages.append(ai)
                if not ai.tool_calls:
                    outcome.notes = str(ai.content).strip()
                    break
                for call in ai.tool_calls:
                    try:
                        parsed = await execute(call["name"], call.get("args") or {})
                        content = json.dumps(parsed, default=str)[:6000]
                    except ToolDenied as denied:
                        outcome.errors.append({"agent": agent, "tool": call["name"], "error": "denied", "message": denied.reason})
                        content = json.dumps({"ok": False, "error": "not_authorized", "message": denied.reason})
                    messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
        except ProviderFailure as exc:
            outcome.llm_used = False
            outcome.errors.append({"agent": agent, "error": "llm_unavailable", "message": exc.code})
            logger.warning("specialist LLM unavailable — deterministic plan", extra={"agent": agent, "error": exc.code})

    # 2) Deterministic coverage: run required tools the model skipped (or all of them when the LLM was down)
    for name, args in required_calls(agent, intent, skus, state):
        if name in outcome.results or name not in allowed:
            continue
        try:
            await execute(name, args)
        except ToolDenied as denied:
            outcome.errors.append({"agent": agent, "tool": name, "error": "denied", "message": denied.reason})

    outcome.calls = list(ctx.calls)
    outcome.duration_ms = round((time.perf_counter() - started) * 1000)
    return outcome
