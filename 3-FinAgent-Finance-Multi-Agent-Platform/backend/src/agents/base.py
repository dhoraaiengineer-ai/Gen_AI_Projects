"""Agent framework (docs/agent-design.md).

Every specialist:
1. optionally lets an LLM pick tools in a **bounded loop** (``max_tool_iterations``), restricted to
   the agent's allow-list and called through **MCP**;
2. runs any **required** tool the model skipped (or all of them when no LLM is available —
   the deterministic fallback plan);
3. builds **highlights from tool facts in code** (the LLM never produces the numbers);
4. computes a **confidence** score from what actually succeeded.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.core.errors import AppError
from src.core.metrics import AGENT_LATENCY, AGENT_RUNS
from src.core.tokens import estimate_tokens, trim_to_tokens
from src.core.tracing import set_attributes, span
from src.guardrails.checks import sanitise_untrusted
from src.tools.base import ToolContext, ToolResult
from src.tools.permissions import AGENT_TOOLS

logger = logging.getLogger(__name__)

ToolSource = Literal["llm", "required", "fallback"]


class AgentTask(BaseModel):
    task: str
    question: str
    portfolio_id: str | None = None
    tickers: list[str] = Field(default_factory=list)
    upstream: dict[str, list[str]] = Field(default_factory=dict)  # agent → highlights
    upstream_data: dict[str, dict[str, Any]] = Field(default_factory=dict)  # agent → extra


class ToolCallSummary(BaseModel):
    tool: str
    ok: bool
    via: ToolSource
    error_code: str | None = None
    duration_ms: float = 0.0


class Evidence(BaseModel):
    source: str  # tool name or document
    citation: str  # human-readable reference
    url: str | None = None
    as_of: str | None = None


class AgentResult(BaseModel):
    agent: str
    task: str
    status: Literal["ok", "partial", "failed", "skipped"]
    highlights: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)  # tool name → data
    evidence: list[Evidence] = Field(default_factory=list)
    interpretation: str | None = None
    confidence: float = 0.0
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    llm_used: bool = False
    duration_ms: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)


class ToolCaller(Protocol):
    async def call(self, tool: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...


ToolSchemas = Callable[[Sequence[str]], list[dict[str, Any]]]
AgentModelFactory = Callable[[list[dict[str, Any]]], Runnable[Any, Any]]


@dataclass
class AgentDeps:
    tools: ToolCaller  # MCP gateway
    tool_schemas: ToolSchemas  # OpenAI-style function schemas for named tools
    model_factory: AgentModelFactory | None  # None = deterministic mode (no LLM)
    max_tool_iterations: int = 2
    max_input_tokens: int = 3_000  # per tool-selection call (ADR-029)
    tool_result_max_tokens: int = 450  # each tool result shown back to the model


@dataclass
class _Run:
    results: dict[str, ToolResult] = field(default_factory=dict)
    calls: list[ToolCallSummary] = field(default_factory=list)
    interpretation: str | None = None
    llm_used: bool = False
    errors: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    name: str = ""
    description: str = ""
    tasks: tuple[str, ...] = ()
    llm_tools: tuple[str, ...] = ()  # tools offered to the LLM (subset of the allow-list)

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps
        unknown = set(self.llm_tools) - AGENT_TOOLS.get(self.name, frozenset())
        if unknown:
            raise ValueError(f"{self.name}: tools not in allow-list: {sorted(unknown)}")

    # ------------------------------------------------------------------ to implement
    @abstractmethod
    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        """Tool calls that must happen for this task (also the fallback plan)."""

    @abstractmethod
    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        """Highlights (plain sentences built from tool data) and extra structured output."""

    def evidence(self, results: dict[str, ToolResult]) -> list[Evidence]:
        return [
            Evidence(source=name, citation=f"{name} ({r.source})")
            for name, r in results.items()
            if r.ok
        ]

    def system_prompt(self, ctx: ToolContext) -> str:
        return (
            f"You are the FinAgent {self.name} agent: {self.description}\n"
            f"User role: {ctx.role.value}. You may call only the tools provided.\n"
            "Never calculate financial metrics yourself; call tools. Use the portfolio id and "
            "tickers given. When you have what you need, reply with at most two short sentences "
            "and no numbers that did not come from a tool."
        )

    # ------------------------------------------------------------------ execution
    async def run(self, task: AgentTask, ctx: ToolContext) -> AgentResult:
        with span(f"agent {self.name}", agent=self.name, task=task.task):
            result = await self._run(task, ctx)
            set_attributes(status=result.status, confidence=result.confidence)
            return result

    async def _run(self, task: AgentTask, ctx: ToolContext) -> AgentResult:
        started = time.perf_counter()
        agent_ctx = ToolContext(
            role=ctx.role,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            agent=self.name,
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
        )
        state = _Run()
        required = self.required_calls(task)
        if self.deps.model_factory is not None and self.llm_tools:
            await self._llm_loop(task, agent_ctx, state)
        for tool, args in required:
            if tool not in state.results or not state.results[tool].ok:
                via: ToolSource = "required" if state.llm_used else "fallback"
                await self._call(tool, args, agent_ctx, state, via)
        try:
            highlights, extra = self.summarise(task, state.results)
        except Exception as exc:  # summaries must not lose the facts
            logger.exception("summary failed", extra={"agent": self.name})
            highlights, extra = [], {}
            state.errors.append(f"summary failed: {type(exc).__name__}")
        ok_required = sum(1 for t, _ in required if state.results.get(t) and state.results[t].ok)
        status = "ok" if ok_required == len(required) else ("partial" if ok_required else "failed")
        duration = (time.perf_counter() - started) * 1000
        AGENT_RUNS.labels(agent=self.name, status=status).inc()
        AGENT_LATENCY.labels(agent=self.name).observe(duration / 1000)
        return AgentResult(
            agent=self.name,
            task=task.task,
            status=status,
            highlights=highlights,
            facts={k: v.data for k, v in state.results.items() if v.ok},
            evidence=self.evidence({k: v for k, v in state.results.items() if v.ok}),
            interpretation=state.interpretation,
            confidence=self.confidence(required, state),
            tool_calls=state.calls,
            errors=self._open_errors(state),
            llm_used=state.llm_used,
            duration_ms=round(duration, 1),
            extra=extra,
        )

    @staticmethod
    def _open_errors(state: _Run) -> list[str]:
        """Errors still relevant: deduplicated, minus tool errors for tools that later succeeded
        (e.g. the model tried an unknown ticker, then the right one)."""
        succeeded = {name for name, r in state.results.items() if r.ok}
        return [e for e in dict.fromkeys(state.errors) if e.split(":", 1)[0] not in succeeded]

    def confidence(self, required: list[tuple[str, dict[str, Any]]], state: _Run) -> float:
        """Share of required tools that succeeded, discounted when the LLM path was unavailable."""
        if not required:
            return 0.5
        ok = sum(1 for t, _ in required if state.results.get(t) and state.results[t].ok)
        score = ok / len(required)
        if not state.llm_used and self.deps.model_factory is not None:
            score *= 0.9  # LLM fell back: facts intact, interpretation missing
        return round(score, 2)

    async def _call(
        self, tool: str, args: dict[str, Any], ctx: ToolContext, state: _Run, via: ToolSource
    ) -> ToolResult:
        result = await self.deps.tools.call(tool, args, ctx)
        previous = state.results.get(tool)
        if result.ok or previous is None or not previous.ok:  # a failure never hides a success
            state.results[tool] = result
        state.calls.append(
            ToolCallSummary(
                tool=tool,
                ok=result.ok,
                via=via,
                error_code=result.error.code if result.error else None,
                duration_ms=result.duration_ms,
            )
        )
        if not result.ok and result.error:
            state.errors.append(f"{tool}: {result.error.code}")
        return result

    async def _llm_loop(self, task: AgentTask, ctx: ToolContext, state: _Run) -> None:
        if self.deps.model_factory is None:
            return
        try:
            model = self.deps.model_factory(self.deps.tool_schemas(self.llm_tools))
        except AppError as exc:
            state.errors.append(f"llm unavailable: {exc.code}")
            return
        messages: list[BaseMessage] = [
            SystemMessage(self.system_prompt(ctx)),
            HumanMessage(self._task_text(task)),
        ]
        schema_tokens = estimate_tokens(str(self.deps.tool_schemas(self.llm_tools)))
        for _ in range(self.deps.max_tool_iterations):
            prompt_tokens = schema_tokens + sum(estimate_tokens(str(m.content)) for m in messages)
            if prompt_tokens > self.deps.max_input_tokens:
                state.errors.append("llm step skipped: input token budget reached")
                return  # required tools still run deterministically
            try:
                reply = await model.ainvoke(messages)
            except AppError as exc:
                state.errors.append(f"llm failed: {exc.code}")
                logger.warning(
                    "agent llm failed; using deterministic plan",
                    extra={"agent": self.name, "error": exc.code},
                )
                return
            state.llm_used = True
            if not isinstance(reply, AIMessage) or not reply.tool_calls:
                state.interpretation = str(getattr(reply, "content", "") or "").strip() or None
                return
            messages.append(reply)
            for call in reply.tool_calls:
                name = call["name"]
                if name not in self.llm_tools:
                    content = json.dumps({"error": f"tool {name} not available to this agent"})
                else:
                    result = await self._call(name, dict(call["args"]), ctx, state, "llm")
                    content = _tool_text(result, self.deps.tool_result_max_tokens)
                messages.append(ToolMessage(content, tool_call_id=call.get("id") or name))

    def _task_text(self, task: AgentTask) -> str:
        lines = [f"Task: {task.task}", f"User question: {task.question}"]
        if task.portfolio_id:
            lines.append(f"Portfolio id: {task.portfolio_id}")
        if task.tickers:
            lines.append(f"Tickers: {', '.join(task.tickers)}")
        for agent, highlights in task.upstream.items():
            lines.append(f"From {agent} agent: " + " ".join(highlights[:4]))
        return "\n".join(lines)


def _tool_text(result: ToolResult, max_tokens: int) -> str:
    """Compact JSON of a tool result for the model (untrusted data, token-bounded)."""
    payload = (
        result.data if result.ok else {"error": result.error.model_dump() if result.error else None}
    )
    text, _ = sanitise_untrusted(json.dumps(payload, default=str, separators=(",", ":")))
    return trim_to_tokens(text, max_tokens)


def pct(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def pct_exact(value: float | None) -> str:
    """Thresholds and limits: as many decimals as needed, no rounding (0.025 → '2.5%')."""
    if value is None:
        return "n/a"
    text = f"{value * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def money(value: float | None) -> str:
    if value is None:
        return "n/a"
    for unit, size in (("bn", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(value) >= size:
            return f"${value / size:,.1f}{unit}"
    return f"${value:,.0f}"
