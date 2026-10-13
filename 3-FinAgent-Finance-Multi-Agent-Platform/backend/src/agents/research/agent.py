"""Research agent: grounded answers from the knowledge base (cited) plus company fundamentals
(ratios from reported statements) for the tickers in the question."""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentTask, BaseAgent, Evidence, pct
from src.agents.research.prompts import DESCRIPTION
from src.tools.base import ToolResult

REFUSAL_PREFIX = "I can't answer that from the documents"


class ResearchAgent(BaseAgent):
    name = "research"
    description = DESCRIPTION
    tasks = ("research", "answer_question")
    llm_tools = ("search_documents", "get_ratios", "search_financial_reports", "valuation_dcf")

    def required_calls(self, task: AgentTask) -> list[tuple[str, dict[str, Any]]]:
        calls: list[tuple[str, dict[str, Any]]] = [
            ("answer_from_documents", {"question": task.question[:500], "k": 5})
        ]
        if task.tickers:
            calls.append(("get_ratios", {"ticker": task.tickers[0]}))
        return calls

    def summarise(
        self, task: AgentTask, results: dict[str, ToolResult]
    ) -> tuple[list[str], dict[str, Any]]:
        out: list[str] = []
        extra: dict[str, Any] = {}
        answer = _data(results, "answer_from_documents")
        if answer:
            text = str(answer.get("answer", "")).strip()
            extra |= {
                "answer": text,
                "answerSource": answer.get("answerSource"),
                "citations": answer.get("citations", []),
                "kbVersion": answer.get("kbVersion"),
            }
            if text and not text.startswith(REFUSAL_PREFIX):
                out.append(f"From the knowledge base: {text}")
                for c in answer.get("citations", [])[:4]:
                    out.append(f"[{c['n']}] {c['citation']}")
            else:
                out.append("The knowledge base has no document that answers this question.")
        ratios = _data(results, "get_ratios")
        if ratios and ratios.get("periods"):
            last = ratios["periods"][-1]
            parts = [
                f"gross margin {pct(last.get('gross_margin'))}",
                f"operating margin {pct(last.get('operating_margin'))}",
            ]
            if last.get("revenue_growth") is not None:
                parts.append(f"revenue growth {pct(last['revenue_growth'])}")
            if last.get("net_debt_to_ebitda") is not None:
                parts.append(f"net debt/EBITDA {last['net_debt_to_ebitda']:.1f}x")
            out.append(f"{ratios['ticker']} FY{last['fiscalYear']}: " + ", ".join(parts) + ".")
            extra["ratios"] = ratios["periods"]
        return out, extra

    def evidence(self, results: dict[str, ToolResult]) -> list[Evidence]:
        evidence: list[Evidence] = []
        answer = _data(results, "answer_from_documents")
        for c in (answer or {}).get("citations", []):
            evidence.append(Evidence(source="knowledge_base", citation=str(c["citation"])))
        if _data(results, "get_ratios"):
            evidence.append(Evidence(source="get_ratios", citation="reported financial statements"))
        return evidence


def _data(results: dict[str, ToolResult], tool: str) -> dict[str, Any] | None:
    result = results.get(tool)
    return result.data if result and result.ok and isinstance(result.data, dict) else None
