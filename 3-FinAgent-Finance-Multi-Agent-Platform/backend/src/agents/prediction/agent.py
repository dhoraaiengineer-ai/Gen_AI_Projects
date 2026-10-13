"""Prediction agent: ML forecasts with intervals — 21-day return/volatility per ticker, next-year
financial metric, next-quarter portfolio risk. Every output is labelled ML PREDICTION and carries
the model version and "not a guarantee"."""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentTask, BaseAgent, Evidence, pct
from src.agents.prediction.prompts import DESCRIPTION
from src.tools.base import ToolResult


class PredictionAgent(BaseAgent):
    name = "prediction"
    description = DESCRIPTION
    tasks = ("forecast",)
    llm_tools = ("predict_market_trend", "predict_financial_metric", "predict_risk")

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        calls: list[tuple[str, dict[str, Any]]] = []
        if task.tickers:
            ticker = task.tickers[0]
            calls.append(("predict_market_trend", {"ticker": ticker}))
            if "revenue" in task.question.lower() or "earnings" in task.question.lower():
                calls.append(("predict_financial_metric", {"ticker": ticker, "metric": "revenue"}))
        elif task.portfolio_id:
            calls.append(("predict_risk", {"portfolio_id": task.portfolio_id}))
        return calls

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        extra: dict[str, Any] = {}
        trend = _data(results, "predict_market_trend")
        if trend:
            ret, vol = trend["returnLog"], trend["volatilityAnnualised"]
            r_iv, v_iv = ret["predictionInterval"], vol["predictionInterval"]
            out.append(
                f"ML PREDICTION: {trend['ticker']} {trend['horizonDays']}-day log return "
                f"{pct(ret['prediction'])} (80% interval {pct(r_iv['lower'])} to "
                f"{pct(r_iv['upper'])}), direction {trend['direction']}; {trend['modelVersion']}; "
                "not a guarantee."
            )
            out.append(
                f"ML PREDICTION: {trend['ticker']} annualised volatility {pct(vol['prediction'])} "
                f"(80% interval {pct(v_iv['lower'])} to {pct(v_iv['upper'])}); not a guarantee."
            )
            extra["forecast"] = trend
            extra["uncertainty"] = trend.get("uncertainty", [])
        metric = _data(results, "predict_financial_metric")
        if metric:
            iv = metric["predictionInterval"]
            out.append(
                f"ML PREDICTION: {metric['ticker']} {metric['period']} {metric['metric']} "
                f"${metric['prediction'] / 1e9:,.2f}bn (80% interval ${iv['lower'] / 1e9:,.2f}bn "
                f"to ${iv['upper'] / 1e9:,.2f}bn; trend model {metric['modelVersion']}); "
                "not a guarantee."
            )
            extra["metricForecast"] = metric
        risk = _data(results, "predict_risk")
        if risk:
            out.append(
                f"ML PREDICTION: {risk['portfolioId']} next-quarter risk score "
                f"{risk['riskScore']:.0f}/100 ({risk['riskCategory']}, confidence "
                f"{risk['confidence']:.2f}, {risk['modelVersion']}); not a guarantee."
            )
            extra["riskForecast"] = risk
        if not out:
            out.append("Name a ticker (or a portfolio) to produce a forecast.")
        return out, extra

    def evidence(self, results: dict[str, ToolResult]) -> list[Evidence]:
        return [
            Evidence(source=n, citation=f"{n} (ML model, synthetic training data)")
            for n, r in results.items()
            if r.ok
        ]


def _data(results: dict[str, ToolResult], tool: str) -> dict[str, Any] | None:
    result = results.get(tool)
    return result.data if result and result.ok and isinstance(result.data, dict) else None
