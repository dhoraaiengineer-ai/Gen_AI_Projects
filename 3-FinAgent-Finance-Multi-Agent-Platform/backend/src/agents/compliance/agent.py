"""Compliance agent: policy validation and the human-approval decision.

Approval rules are deterministic (never delegated to an LLM or decision model):
* any **hard** limit breach → approval required for any action on the portfolio;
* draft orders above ``APPROVAL_VALUE_THRESHOLD`` → approval required.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentDeps, AgentTask, BaseAgent, money, pct, pct_exact
from src.agents.compliance.prompts import DESCRIPTION
from src.tools.base import ToolResult


class ComplianceAgent(BaseAgent):
    name = "compliance"
    description = DESCRIPTION
    tasks = ("validate",)
    llm_tools = ()  # deterministic: rules only

    def __init__(self, deps: AgentDeps, approval_threshold: float = 250_000) -> None:
        super().__init__(deps)
        self.approval_threshold = approval_threshold

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        if not task.portfolio_id:
            return []
        return [("check_policy_limits", {"portfolio_id": task.portfolio_id})]

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        reasons: list[str] = []
        limits = results.get("check_policy_limits")
        checks = (
            limits.data["checks"] if limits and limits.ok and isinstance(limits.data, dict) else []
        )
        hard = [c for c in checks if c["breached"] and c["severity"] == "hard"]
        warnings = [c for c in checks if c["breached"] and c["severity"] != "hard"]
        for c in hard:
            reasons.append(
                f"hard limit breach: {c['subject']} at {pct(c['actual'])} vs {pct_exact(c['threshold'])}"
            )
        orders_value = float(task.upstream_data.get("portfolio", {}).get("draftOrdersValue") or 0.0)
        if orders_value > self.approval_threshold:
            reasons.append(
                f"draft orders {money(orders_value)} exceed the {money(self.approval_threshold)} threshold"
            )
        status = "block" if hard and orders_value else "flag" if (hard or warnings) else "pass"
        if hard:
            out.append(
                f"Compliance: {len(hard)} hard limit breach(es) — any change to this portfolio "
                "requires portfolio-manager or compliance approval."
            )
        if warnings:
            out.append(f"Compliance: {len(warnings)} warning-level breach(es) to monitor.")
        if not checks and limits is None:
            out.append("Compliance: no portfolio in scope; nothing to validate.")
        elif status == "pass":
            out.append("Compliance: all checks passed.")
        out.append(
            "Decision support only — not investment advice; no orders are executed automatically."
        )
        return out, {
            "status": status,
            "approvalRequired": bool(reasons),
            "approvalReasons": reasons,
            "hardBreaches": hard,
            "warningBreaches": warnings,
        }
