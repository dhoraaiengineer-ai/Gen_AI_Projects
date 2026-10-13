"""BaseAgent bookkeeping: a failed retry never hides a success; resolved errors are not reported."""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentDeps, AgentTask, BaseAgent
from src.core.domain import Role
from src.tools.base import ToolContext, ToolError, ToolResult


class Tools:
    def __init__(self, good: set[str]) -> None:
        self.good = good

    async def call(self, tool: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if args.get("ticker") in self.good:
            return ToolResult(ok=True, tool=tool, data={"ticker": args["ticker"]})
        return ToolResult(
            ok=False, tool=tool, error=ToolError(code="not_found", message="unknown ticker")
        )


class Probe(BaseAgent):
    name = "market"
    description = "test agent"
    tasks = ("probe",)

    def __init__(self, deps: AgentDeps, calls: list[tuple[str, dict[str, Any]]]) -> None:
        super().__init__(deps)
        self.calls = calls

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        return self.calls

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        return [], {}


def _agent(calls: list[tuple[str, dict[str, Any]]]) -> Probe:
    deps = AgentDeps(tools=Tools({"NVTK"}), tool_schemas=lambda n: [], model_factory=None)
    return Probe(deps, calls)


TASK = AgentTask(task="probe", question="q")
CTX = ToolContext(role=Role.ANALYST, tenant_id="t")


async def test_failure_after_success_keeps_the_success_and_hides_resolved_error() -> None:
    agent = _agent(
        [("get_stock_price", {"ticker": "NVTK"}), ("get_stock_price", {"ticker": "SEMIS"})]
    )
    result = await agent.run(TASK, CTX)
    assert result.status == "ok" and result.facts["get_stock_price"] == {"ticker": "NVTK"}
    assert result.errors == []
    assert [c.ok for c in result.tool_calls] == [True]  # second required call skipped: already ok


async def test_unresolved_errors_are_reported_once() -> None:
    agent = _agent([("get_stock_price", {"ticker": "NOPE"}), ("get_news", {"ticker": "X"})])
    result = await agent.run(TASK, CTX)
    assert result.status == "failed"
    assert result.errors == ["get_stock_price: not_found", "get_news: not_found"]
