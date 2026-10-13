"""Structured analysis endpoints (portfolio, risk, fraud, research, predict, agents/run).

Each turns typed input into a supervisor run with a **known intent** (no classification call), so
the same agents, guardrails, approvals and audit apply as for chat.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.container import Container
from src.core.errors import ValidationFailed
from src.presenters.chat import ChatPresenter
from src.schemas.views import AnalyzeRequest, ChatResponse
from src.security.auth import Principal


@dataclass(frozen=True)
class Kind:
    intent: str
    needs: str  # "portfolio" | "ticker" | "transaction_or_customer" | "question" | ""
    template: str


KINDS: dict[str, Kind] = {
    "portfolio": Kind("portfolio_overview", "portfolio", "Give an overview of portfolio {p}."),
    "risk": Kind("executive_report", "portfolio", "Complete risk review of portfolio {p}."),
    "rebalance": Kind("rebalance", "portfolio", "Propose a rebalance for portfolio {p}."),
    "compliance": Kind("compliance_check", "portfolio", "Check portfolio {p} against limits."),
    "fraud": Kind(
        "fraud_detection", "transaction_or_customer", "Is {subject} fraudulent or suspicious?"
    ),
    "research": Kind("company_analysis", "ticker", "Analyse {t}: financials and valuation."),
    "predict": Kind("forecast", "ticker", "Forecast {t} return and volatility for next month."),
    "agents": Kind("", "question", "{q}"),
}


class AnalysisPresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    async def run(
        self, kind: str, principal: Principal, body: AnalyzeRequest, request_id: str | None
    ) -> ChatResponse:
        spec = KINDS[kind]
        p = (body.portfolio_id or "").upper()
        t = (body.ticker or "").upper()
        subject = body.transaction_id or body.customer_id or ""
        if spec.needs == "portfolio" and not p:
            raise ValidationFailed("portfolioId is required")
        if spec.needs == "ticker" and not t:
            raise ValidationFailed("ticker is required")
        if spec.needs == "transaction_or_customer" and not subject:
            raise ValidationFailed("transactionId or customerId is required")
        if spec.needs == "question" and not body.question:
            raise ValidationFailed("question is required")
        question = body.question or spec.template.format(p=p, t=t, subject=subject, q="")
        forced = (
            {"intent": spec.intent, "portfolio_id": p or None, "tickers": [t] if t else []}
            if spec.intent
            else None
        )
        memory = self.container.memory
        runner = await self.container.supervisor()
        cid = await memory.start(body.conversation_id, principal.user_id, question)
        history = await memory.history(principal.tenant_id, cid)
        report = await runner.run(
            question,
            ChatPresenter._caller(principal),
            request_id=request_id,
            history=history,
            forced=forced,
        )
        await memory.remember(principal.tenant_id, cid, question, report)
        return ChatResponse(
            request_id=str(report.get("requestId")), report=report, conversation_id=cid or None
        )
