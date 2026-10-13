"""Risk agent: VaR, volatility change attribution, limits, risk score, stress."""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentTask, BaseAgent, money, pct, pct_exact
from src.agents.risk.prompts import DESCRIPTION
from src.core.domain import RISK_LEVELS
from src.tools.base import ToolResult


class RiskAgent(BaseAgent):
    name = "risk"
    description = DESCRIPTION
    tasks = ("calculate_risk", "explain_risk_change")
    llm_tools = (
        "calculate_var",
        "explain_risk_change",
        "check_policy_limits",
        "calculate_risk_score",
        "stress_test",
    )

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        if not task.portfolio_id:
            return []
        pid = {"portfolio_id": task.portfolio_id}
        return [
            ("calculate_var", {**pid, "confidence": 0.95}),
            ("explain_risk_change", pid),
            ("check_policy_limits", pid),
            ("calculate_risk_score", pid),
        ]

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        extra: dict[str, Any] = {}
        var = _data(results, "calculate_var")
        if var:
            out.append(
                f"1-day {int(var['confidence'] * 100)}% historical VaR is {pct(var['var'], 2)} "
                f"({money(var['var_amount'])}); expected shortfall {pct(var['cvar'], 2)}."
            )
            extra["var95"] = var["var"]
        change = _data(results, "explain_risk_change")
        if change:
            out.append(
                f"Annualised volatility rose from {pct(change['volatilityBefore'])} to "
                f"{pct(change['volatilityAfter'])} over the last {change['windowDays']} trading days: "
                f"{pct(change['marketEffect'])} from market moves and "
                f"{pct(change['weightsEffect'])} from position changes."
            )
            top = change["topContributors"][:2]
            for i, c in enumerate(top):
                verb = "contributed most" if i == 0 else "also contributed"
                out.append(
                    f"{c['ticker']} ({c['sector']}) {verb}: weight "
                    f"{pct(c['weightBefore'])} → {pct(c['weightAfter'])}, volatility "
                    f"{pct(c['volatilityBefore'])} → {pct(c['volatilityAfter'])}."
                )
            extra["riskChange"] = change
        limits = _data(results, "check_policy_limits")
        if limits:
            breaches = [c for c in limits["checks"] if c["breached"]]
            for c in breaches:
                out.append(
                    f"Limit breach ({c['severity']}): {_subject(c)} at {_actual(c)} vs "
                    f"{pct_exact(c['threshold'])} limit ({c['policyReference'] or 'policy'})."
                )
            if not breaches:
                out.append("All policy limits are within thresholds.")
            extra["breaches"] = breaches
        score = _data(results, "calculate_risk_score")
        if score:
            if score.get("modelVersion"):
                rules = score.get("rulesCrossCheck", {})
                out.append(
                    f"ML PREDICTION: next-quarter risk score {score['riskScore']:.0f}/100 ({score['riskCategory']}, confidence {score['confidence']:.2f}, {score['modelVersion']}); not a guarantee."
                )
                if rules:
                    out.append(
                        f"Rules-based current risk score {rules['riskScore']:.0f}/100 ({rules['riskCategory']}, {rules['method']})."
                    )
                extra["mlRisk"] = {
                    "riskScore": score["riskScore"],
                    "riskCategory": score["riskCategory"],
                    "confidence": score["confidence"],
                    "modelVersion": score["modelVersion"],
                }
                # Overall level is the more severe of the forecast and the current rules view.
                worst = max([score, rules] if rules else [score], key=_severity)
                extra["riskScore"] = worst["riskScore"]
                extra["riskCategory"] = worst["riskCategory"]
            else:
                out.append(
                    f"Risk score {score['riskScore']:.0f}/100 ({score['riskCategory']}, {score['method']})."
                )
                extra["riskScore"] = score["riskScore"]
                extra["riskCategory"] = score["riskCategory"]
        return out, extra


def _severity(score: dict[str, Any]) -> tuple[int, float]:
    return RISK_LEVELS.index(score["riskCategory"]), float(score["riskScore"])


def _subject(check: dict[str, Any]) -> str:
    labels = {"single_name": "single-name", "sector": "sector", "var_95_1d": "1-day 95% VaR",
              "max_drawdown": "max drawdown"}  # fmt: skip
    if check["subject"] == "portfolio":
        return f"portfolio {labels.get(check['limitType'], check['limitType'])}"
    return f"{check['subject']} {labels.get(check['limitType'], check['limitType'])}"


def _actual(check: dict[str, Any]) -> str:
    return pct(check["actual"], 2 if check["limitType"] == "var_95_1d" else 1)


def _data(results: dict[str, ToolResult], tool: str) -> dict[str, Any] | None:
    result = results.get(tool)
    return result.data if result and result.ok and isinstance(result.data, dict) else None
