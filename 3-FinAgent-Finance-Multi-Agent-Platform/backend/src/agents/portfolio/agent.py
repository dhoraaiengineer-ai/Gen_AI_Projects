"""Portfolio agent: holdings, allocation, returns; rebalance drafts on request."""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentTask, BaseAgent, Evidence, money, pct
from src.agents.portfolio.prompts import DESCRIPTION
from src.tools.base import ToolResult


class PortfolioAgent(BaseAgent):
    name = "portfolio"
    description = DESCRIPTION
    tasks = ("portfolio_overview", "propose_rebalance")
    llm_tools = (
        "get_portfolio_summary",
        "get_holdings",
        "calculate_returns",
        "calculate_allocation",
        "calculate_diversification",
    )

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        if not task.portfolio_id:
            return [("list_portfolios", {})]
        pid = {"portfolio_id": task.portfolio_id}
        calls: list[tuple[str, dict[str, Any]]] = [
            ("get_portfolio_summary", pid),
            ("get_holdings", pid),
            ("calculate_returns", pid),
        ]
        if task.task == "propose_rebalance":
            calls.append(("propose_rebalance", pid))
        return calls

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        extra: dict[str, Any] = {}
        summary = _data(results, "get_portfolio_summary")
        if summary:
            top = summary["topHoldings"][0] if summary["topHoldings"] else None
            out.append(
                f"{summary['name']} ({summary['portfolio']}) is worth {money(summary['nav'])} as of "
                f"{summary['priceDate']}, with {pct(summary['cash'] / summary['nav'])} in cash."
            )
            if top:
                out.append(
                    f"The largest holding is {top['ticker']} at {pct(top['weight'])} of the portfolio."
                )
            sectors = summary.get("sectorWeights") or {}
            if sectors:
                name, weight = next(iter(sectors.items()))
                out.append(f"The largest sector is {name} at {pct(weight)}.")
            extra["portfolio"] = {
                "id": summary["portfolio"],
                "name": summary["name"],
                "nav": summary["nav"],
            }
        holdings = _data(results, "get_holdings")
        if holdings:
            extra["holdings"] = [
                {
                    k: h[k]
                    for k in ("ticker", "name", "sector", "weight", "value", "riskContribution")
                }
                for h in holdings["holdings"]
            ]
            extra["topTickers"] = [h["ticker"] for h in holdings["holdings"][:3]]
        returns = _data(results, "calculate_returns")
        if returns and "1y" in returns["returns"]:
            r = returns["returns"]["1y"]
            out.append(
                f"Over one year the holdings returned {pct(r['portfolio'])} versus "
                f"{pct(r['benchmark'])} for the {returns['benchmark']} benchmark."
            )
        rebalance = _data(results, "propose_rebalance")
        if rebalance:
            extra["draftOrders"] = rebalance["orders"]
            extra["draftOrdersValue"] = rebalance["totalValue"]
            out.append(
                f"A draft rebalance of {len(rebalance['orders'])} orders worth "
                f"{money(rebalance['totalValue'])} was prepared; it requires human approval."
            )
        listing = _data(results, "list_portfolios")
        if listing:
            names = ", ".join(f"{p['portfolioId']} ({p['name']})" for p in listing["portfolios"])
            out.append(f"Available portfolios: {names}.")
        return out, extra

    def evidence(self, results: dict[str, ToolResult]) -> list[Evidence]:
        summary = _data(results, "get_portfolio_summary")
        as_of = summary["priceDate"] if summary else None
        return [
            Evidence(source=n, citation=f"{n} (portfolio database, priced {as_of})", as_of=as_of)
            for n, r in results.items()
            if r.ok
        ]


def _data(results: dict[str, ToolResult], tool: str) -> dict[str, Any] | None:
    result = results.get(tool)
    return result.data if result and result.ok and isinstance(result.data, dict) else None
