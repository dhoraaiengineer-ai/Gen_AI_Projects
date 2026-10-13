"""Market agent: benchmark and sector context, indicators and news (cited by URL)."""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentTask, BaseAgent, Evidence, pct
from src.agents.market.prompts import DESCRIPTION
from src.tools.base import ToolResult


class MarketAgent(BaseAgent):
    name = "market"
    description = DESCRIPTION
    tasks = ("market_context",)
    llm_tools = (
        "get_market_summary",
        "get_market_news",
        "get_technical_indicators",
        "get_stock_price",
    )

    def _focus(self, task: AgentTask) -> list[str]:
        upstream = task.upstream_data.get("portfolio", {}).get("topTickers", [])
        return list(dict.fromkeys([*task.tickers, *upstream]))[:3]

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        calls: list[tuple[str, dict[str, Any]]] = [("get_market_summary", {})]
        focus = self._focus(task)
        calls.append(
            ("get_market_news", {"tickers": focus, "query": task.question[:200], "limit": 4})
        )
        if focus:
            calls.append(("get_technical_indicators", {"ticker": focus[0]}))
        return calls

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        extra: dict[str, Any] = {}
        summary = _data(results, "get_market_summary")
        if summary and summary.get("benchmark"):
            b = summary["benchmark"]
            out.append(
                f"The {b['ticker']} benchmark returned {pct(b['return1m'])} over the last month "
                f"with 3-month volatility of {pct(b['volatility3m'])}."
            )
            sectors = summary.get("sectors") or []
            if sectors:
                best, worst = sectors[0], sectors[-1]
                out.append(
                    f"Best sector over one month: {best['sector']} ({pct(best['return1m'])}); "
                    f"weakest: {worst['sector']} ({pct(worst['return1m'])})."
                )
            extra["sectors"] = sectors
        indicators = _data(results, "get_technical_indicators")
        if indicators:
            trend = str(indicators.get("trend", "")).replace("_", " ")
            rsi = indicators.get("rsi_14")
            out.append(
                f"{indicators['ticker']} trades {trend} with RSI(14) at {rsi:.0f}."
                if rsi is not None
                else f"{indicators['ticker']} trades {trend}."
            )
        news = _data(results, "get_market_news")
        if news:
            items = news.get("items", [])
            extra["news"] = items
            for item in items[:3]:
                out.append(f"News ({item.get('published')}): {item['title']}.")
        return out, extra

    def evidence(self, results: dict[str, ToolResult]) -> list[Evidence]:
        evidence = [
            Evidence(source=n, citation=f"{n} (market data)")
            for n, r in results.items()
            if r.ok and n != "get_market_news"
        ]
        news = _data(results, "get_market_news")
        for item in (news or {}).get("items", []):
            evidence.append(
                Evidence(
                    source=item.get("source", "news"),
                    citation=item["title"],
                    url=item.get("url"),
                    as_of=item.get("published"),
                )
            )
        return evidence


def _data(results: dict[str, ToolResult], tool: str) -> dict[str, Any] | None:
    result = results.get(tool)
    return result.data if result and result.ok and isinstance(result.data, dict) else None
