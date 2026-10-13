"""Fraud agent: scores a transaction or a customer's recent activity with the fraud model
(LightGBM + Isolation Forest), adds customer context and policy evidence. Read-only: it never
blocks cards or accounts — it recommends analyst review."""

from __future__ import annotations

import re
from typing import Any

from src.agents.base import AgentTask, BaseAgent, Evidence
from src.agents.fraud.prompts import DESCRIPTION
from src.tools.base import ToolResult

TX_RE = re.compile(r"\bTX-\d{6,9}\b", re.IGNORECASE)
CU_RE = re.compile(r"\bCU-\d{6}\b", re.IGNORECASE)


def subjects(question: str) -> tuple[str | None, str | None]:
    tx, cu = TX_RE.search(question), CU_RE.search(question)
    return (tx.group(0).upper() if tx else None, cu.group(0).upper() if cu else None)


class FraudAgent(BaseAgent):
    name = "fraud"
    description = DESCRIPTION
    tasks = ("fraud_review",)
    llm_tools = ("predict_fraud", "detect_anomaly", "get_customer_profile", "get_transactions")

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        tx, cu = subjects(task.question)
        if tx:
            return [
                ("predict_fraud", {"transaction_id": tx}),
                ("get_transactions", {"transaction_id": tx}),
            ]
        if cu:
            return [
                ("predict_fraud", {"customer_id": cu, "days": 183, "limit": 10}),
                ("get_customer_profile", {"customer_id": cu}),
                ("detect_anomaly", {"customer_id": cu, "days": 183}),
            ]
        return []

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        extra: dict[str, Any] = {}
        tx, cu = subjects(task.question)
        if not tx and not cu:
            out.append(
                "Name a transaction (TX-…) or customer (CU-…) id to score it with the fraud model."
            )
            return out, extra
        scored = _data(results, "predict_fraud")
        if scored:
            rows = scored.get("transactions", [])
            metrics = scored.get("modelTestMetrics", {})
            extra |= {
                "flagged": scored.get("flagged", 0),
                "scored": scored.get("scored", 0),
                "transactions": rows,
                "modelVersion": scored.get("modelVersion"),
            }
            if cu:
                out.append(
                    f"Scored {scored['scored']} transactions of {cu} in the last 183 days; "
                    f"{scored['flagged']} rated HIGH or CRITICAL."
                )
            for row in rows[: 3 if cu else 1]:
                reasons = ", ".join(row["reasonCodes"]) or "no dominant factor"
                out.append(
                    f"ML PREDICTION: {row['transactionId']} ({row['merchantCategory']}, "
                    f"${row['amount']:,.2f}, {row['country']}) fraud probability "
                    f"{row['fraudProbability']:.2f}, {row['riskLevel']}; reasons: {reasons}; "
                    f"{row['modelVersion']}; analyst review required."
                )
            if metrics.get("precision") is not None:
                out.append(
                    f"Model test precision {metrics['precision']:.2f} and recall "
                    f"{metrics['recall']:.2f} on synthetic data."
                )
            levels = {r["riskLevel"] for r in rows[:3]}
            extra["actionRequired"] = bool(levels & {"HIGH", "CRITICAL"})
        profile = _data(results, "get_customer_profile")
        if profile:
            out.append(
                f"Customer {profile['customer_code']} is a {profile['segment']} customer based in "
                f"{profile['home_country']} with KYC risk {profile['kyc_risk']}."
            )
        anomalies = _data(results, "detect_anomaly")
        if anomalies:
            out.append(
                f"Isolation Forest flagged {len(anomalies.get('flagged', []))} of "
                f"{anomalies.get('historyCount', 0)} transactions as unusual behaviour."
            )
        if extra.get("actionRequired"):
            out.append(
                "Recommended: route to a fraud analyst; no account action is taken automatically."
            )
        return out, extra

    def evidence(self, results: dict[str, ToolResult]) -> list[Evidence]:
        return [
            Evidence(source=n, citation=f"{n} ({r.source})") for n, r in results.items() if r.ok
        ]


def _data(results: dict[str, ToolResult], tool: str) -> dict[str, Any] | None:
    result = results.get(tool)
    return result.data if result and result.ok and isinstance(result.data, dict) else None
