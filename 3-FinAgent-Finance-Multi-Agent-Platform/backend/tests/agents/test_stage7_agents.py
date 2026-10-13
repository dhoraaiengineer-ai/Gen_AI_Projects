"""Stage 7: fraud / research / prediction agents and human approval via LangGraph interrupt."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from src.core.errors import Conflict, Forbidden
from src.security.audit import AuditService, InMemoryAuditStore
from tests.agents.fakes import FakeTools
from tests.agents.test_supervisor_graph import CALLER, TENANT, Caller, make_runner


class FakeApprovals:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.created = 0

    async def create(self, **kw: Any) -> dict[str, Any]:
        for item in self.items.values():  # idempotent per request
            if item["requestId"] == kw["request_id"]:
                return item
        self.created += 1
        aid = str(uuid.uuid4())
        self.items[aid] = {
            "approvalId": aid,
            "requestId": kw["request_id"],
            "status": "pending",
            "requestedBy": kw["requested_by"],
            "proposal": kw["proposal"],
            "expiresAt": "2026-10-09T00:00:00Z",
        }
        return self.items[aid]

    async def decide(
        self, approval_id: str, *, approve: bool, decided_by: str | None, note: str | None
    ) -> dict[str, Any]:
        item = self.items[approval_id]
        if item["status"] != "pending":
            raise Conflict("already decided")
        if decided_by == item["requestedBy"]:
            raise Forbidden("the requester cannot approve their own proposal")
        item["status"] = "approved" if approve else "rejected"
        orders = item["proposal"]["orders"] if approve else []
        return item | {"decidedBy": decided_by, "draftOrders": orders}


PM = Caller(tenant_id=TENANT, role="portfolio_manager", user_id="u-pm")
FRAUD = Caller(tenant_id=TENANT, role="fraud_analyst", user_id="u-fa")


async def test_fraud_agent_scores_transaction_with_ml_labels() -> None:
    tools = FakeTools()
    runner, _ = make_runner(tools)
    report = await runner.run("Is transaction TX-004512 fraudulent?", FRAUD)
    assert report["intent"] == "fraud_detection"
    assert [a["name"] for a in report["agents"]] == ["fraud"]
    ml = [p["text"] for p in report["sections"]["mlPredictions"]]
    assert ml and "TX-004512" in ml[0] and "0.98, CRITICAL" in ml[0] and "fraud-lgbm@2" in ml[0]
    assert ("predict_fraud", {"transaction_id": "TX-004512"}) in [(t, a) for t, a, _ in tools.calls]


async def test_knowledge_question_uses_rag_answer_without_second_llm() -> None:
    runner, _ = make_runner(FakeTools())
    report = await runner.run("What does our investment policy say about the VaR budget?", CALLER)
    assert report["intent"] == "knowledge_question"
    assert report["sections"]["interpretationSource"] == "rag"
    assert report["sections"]["interpretation"].endswith("2.5% of NAV [1].")
    assert any("Investment_Policy_Statement.docx" in e["citation"] for e in report["evidence"])


async def test_prediction_agent_forecast_is_labelled_not_guaranteed() -> None:
    runner, _ = make_runner(FakeTools())
    report = await runner.run("Forecast NVTK volatility for next month", CALLER)
    assert report["intent"] == "forecast"
    ml = [p["text"] for p in report["sections"]["mlPredictions"]]
    assert len(ml) == 2 and all("not a guarantee" in t for t in ml)
    assert "forecast-lgbm@2" in ml[0]


async def test_rebalance_pauses_for_approval_and_resumes_with_drafts() -> None:
    approvals, store = FakeApprovals(), InMemoryAuditStore()
    runner, _ = make_runner(
        FakeTools(), approvals=approvals, checkpointer=InMemorySaver(), audit=AuditService(store)
    )
    report = await runner.run("Propose a rebalance for Portfolio A", PM)
    pending = report["approval"]
    assert pending["required"] is True and pending["status"] == "pending"
    assert len(pending["draftOrders"]) == 2 and approvals.created == 1

    with pytest.raises(Forbidden):  # requester cannot approve their own proposal
        await runner.resume(report["requestId"], {"approve": True, "decidedBy": "u-pm"})

    final = await runner.resume(
        report["requestId"], {"approve": True, "decidedBy": "u-compliance", "note": "ok"}
    )
    assert final["approval"]["status"] == "approved"
    assert [o["ticker"] for o in final["approval"]["createdDraftOrders"]] == ["NVTK", "ACME"]
    assert approvals.created == 1  # resume re-ran nothing that creates approvals twice
    actions = [(e.action, e.decision) for e in store.events]
    assert ("approval.request", "flag") in actions
    # The decision is audited by the API presenter with the approver's identity, not the graph.
    assert not any(a == "approval.decide" for a, _ in actions)


async def test_rejected_approval_creates_no_orders() -> None:
    approvals = FakeApprovals()
    runner, _ = make_runner(FakeTools(), approvals=approvals, checkpointer=InMemorySaver())
    report = await runner.run("Propose a rebalance for Portfolio A", PM)
    final = await runner.resume(report["requestId"], {"approve": False, "decidedBy": "u-cco"})
    assert final["approval"]["status"] == "rejected"
    assert final["approval"]["createdDraftOrders"] == []


async def test_without_checkpointer_approval_is_recorded_but_not_awaited() -> None:
    approvals = FakeApprovals()
    runner, _ = make_runner(FakeTools(), approvals=approvals)
    report = await runner.run("Propose a rebalance for Portfolio A", PM)
    assert report["approval"]["status"] == "pending" and approvals.created == 1


async def test_resume_refuses_other_tenant_and_unpaused_runs() -> None:
    approvals = FakeApprovals()
    runner, _ = make_runner(FakeTools(), approvals=approvals, checkpointer=InMemorySaver())
    report = await runner.run("Propose a rebalance for Portfolio A", PM)
    other = "0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a02"
    decision = {"approve": True, "decidedBy": "x"}
    with pytest.raises(Conflict):
        await runner.resume(report["requestId"], decision, tenant_id=other)
    assert await runner.pending_approval(report["requestId"], TENANT) is not None
    with pytest.raises(Conflict):
        await runner.resume("no-such-thread", decision)


async def test_follow_up_keeps_the_conversation_portfolio() -> None:
    runner, _ = make_runner(FakeTools())
    history = [{"question": "Risk of B?", "intent": "portfolio_risk", "portfolio": "PF-B"}]
    report = await runner.run("Show me the holdings and allocation", CALLER, history=history)
    assert report["portfolio"] == "PF-B"
    assert any("Follow-up" in a for a in report["sections"]["assumptions"])


async def test_forced_intent_skips_classification() -> None:
    runner, _ = make_runner(FakeTools())
    forced = {"intent": "forecast", "portfolio_id": None, "tickers": ["NVTK"]}
    report = await runner.run("Forecast NVTK", CALLER, forced=forced)
    assert report["intent"] == "forecast" and report["tickers"] == ["NVTK"]
