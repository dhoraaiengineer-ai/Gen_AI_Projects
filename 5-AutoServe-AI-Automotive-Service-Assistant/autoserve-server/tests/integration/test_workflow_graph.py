"""Service graph (P3-3 … P3-8) against real Postgres + the LangGraph PostgresSaver. FakeLLM → template phrasing.

Covers: the 5 scenario routes; interrupts on every human_review route; resume by the right role → transition +
history + audit; wrong role / wrong dealer / missing consent note / missing rationale rejected (graph stays
interrupted); duplicate resume is a no-op; resume after a "process restart" (new checkpointer + new graph objects);
run twice → same business DB state.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.errors import ForbiddenRole, InvalidTransition, NotFound, RationaleRequired, ValidationFailed
from app.core.security import SYSTEM_ACTOR, Actor
from app.graph.deps import NodeDeps
from app.graph.service import DecisionIn, resume_claim, resume_estimate, run_ro_workflow
from app.graph.workflow import postgres_checkpointer
from app.models import (
    AuditLog,
    EstimateLine,
    Notification,
    RepairOrder,
    ReviewDecision,
    RiskFlag,
    ROStatusHistory,
    Vehicle,
    WarrantyClaim,
    WarrantyFinding,
)
from app.models.enums import ClaimStatus, Role, ROStatus
from app.services.demo_adapters import DemoOemAdapter
from app.services.llm_service import FakeLLM
from app.services.state_machine import transition
from scripts.workflow_scenarios import SCENARIOS, create_scenario_ro

pytestmark = pytest.mark.integration
BY_KEY = {s.key: s for s in SCENARIOS}


@pytest.fixture
def deps(ingested: dict[str, object]) -> NodeDeps:
    from app.core.db import get_sessionmaker

    return NodeDeps(sessionmaker=get_sessionmaker(), llm=FakeLLM())


@pytest.fixture
async def saver(deps: NodeDeps) -> AsyncIterator[Any]:
    async with postgres_checkpointer() as cp:
        yield cp


async def _new_ro(deps: NodeDeps, key: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """(ro_id, dealer_id, owner_id)"""
    async with deps.sessionmaker() as s, s.begin():
        ro = await create_scenario_ro(s, BY_KEY[key])
        owner = await s.scalar(select(Vehicle.owner_id).where(Vehicle.id == ro.vehicle_id))
        return ro.id, ro.dealer_id, owner  # type: ignore[return-value]


async def _staff(deps: NodeDeps, dealer_id: uuid.UUID, role: str) -> Actor:
    from app.models import RoleRow, User

    async with deps.sessionmaker() as s:
        uid = await s.scalar(select(User.id).join(RoleRow).where(User.dealer_id == dealer_id, RoleRow.name == role))
    assert uid is not None
    return Actor(uid, role, dealer_id)


def advisor(dealer_id: uuid.UUID) -> Actor:
    return Actor(uuid.uuid4(), Role.SERVICE_ADVISOR, dealer_id)


async def _status(deps: NodeDeps, ro_id: uuid.UUID) -> str:
    async with deps.sessionmaker() as s:
        return (await s.get(RepairOrder, ro_id)).status  # type: ignore[union-attr]


async def _send_estimate(deps: NodeDeps, ro_id: uuid.UUID, dealer_id: uuid.UUID) -> None:
    """Advisor sends the estimate (RO-T07) — the API endpoint arrives with P3-9."""
    from app.models import RoleRow, User

    async with deps.sessionmaker() as s, s.begin():
        adv = await s.scalar(
            select(User).join(RoleRow).where(User.dealer_id == dealer_id, RoleRow.name == "service_advisor")
        )
        ro = await s.get(RepairOrder, ro_id)
        await transition(s, ro, ROStatus.AWAITING_OWNER_APPROVAL, Actor(adv.id, Role.SERVICE_ADVISOR, dealer_id))  # type: ignore[arg-type,union-attr]


@pytest.mark.parametrize("key", [s.key for s in SCENARIOS])
async def test_scenario_routes(deps: NodeDeps, saver: Any, key: str) -> None:
    ro_id, dealer_id, _ = await _new_ro(deps, key)
    result = await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))
    sc = BY_KEY[key]
    assert result.values["route"]["next"] == sc.expect_route
    nodes = [t["node"] for t in result.values["execution_trace"]]
    assert nodes[:8] == ["intake", "vehicle_context", "document", "diagnosis", "warranty", "estimate", "risk", "route"]
    if sc.expect_route == "human_review":
        assert (
            result.waiting_for and result.waiting_for["kind"] == "estimate_approval"
        )  # interrupt on every review route
        assert await _status(deps, ro_id) == ROStatus.ESTIMATE_READY
    if key == "missing":
        assert await _status(deps, ro_id) == ROStatus.INFO_PENDING and result.waiting_for is None
    if key == "recall":
        assert await _status(deps, ro_id) == ROStatus.DIAGNOSING  # advisor confirms the recall job
        est = result.values["estimate"]
        assert {ln["pay_type"] for ln in est["lines"]} == {"recall"}
    if key == "customer":
        assert result.values["warranty"]["overall"] == "not_eligible" and result.claim_thread is None
        assert result.values["estimate"]["totals"]["warranty"] == "0.00"
    if key == "clean":
        assert result.values["warranty"]["overall"] == "eligible" and result.claim_thread
    if key == "high_risk":
        flagged = {d["detector_id"] for d in result.values["risk"]["detections"] if d["status"] == "flag"}
        assert {"D-01", "D-04"} <= flagged and result.values["risk"]["level"] == "high"
        assert any("risk level high" in r for r in result.values["route"]["reasons"])


async def _business_state(deps: NodeDeps, ro_id: uuid.UUID) -> dict[str, Any]:
    async with deps.sessionmaker() as s:
        claim_ids = list(await s.scalars(select(WarrantyClaim.id).where(WarrantyClaim.ro_id == ro_id)))
        return {
            "status": (await s.get(RepairOrder, ro_id)).status,  # type: ignore[union-attr]
            "history": await s.scalar(
                select(func.count()).select_from(ROStatusHistory).where(ROStatusHistory.ro_id == ro_id)
            ),
            "lines": sorted(
                (ln.kind, ln.op_code, ln.part_number, str(ln.amount), ln.pay_type)
                for ln in await s.scalars(select(EstimateLine).where(EstimateLine.ro_id == ro_id))
            ),
            "claims": len(claim_ids),
            "findings": await s.scalar(
                select(func.count()).select_from(WarrantyFinding).where(WarrantyFinding.claim_id.in_(claim_ids))
            ),
            "flags": await s.scalar(select(func.count()).select_from(RiskFlag).where(RiskFlag.ro_id == ro_id)),
            "audit": await s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == ro_id)),
        }


async def test_run_twice_same_db_state(deps: NodeDeps, saver: Any) -> None:
    ro_id, dealer_id, _ = await _new_ro(deps, "high_risk")
    first = await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))
    before = await _business_state(deps, ro_id)
    second = await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))  # thread is waiting → no new run
    assert await _business_state(deps, ro_id) == before
    assert second.waiting_for == first.waiting_for


async def test_rerun_with_identical_inputs_uses_cached_node_outputs(deps: NodeDeps, saver: Any) -> None:
    """INFO_PENDING runs end; a second run (no new documents) recomputes nothing and writes no new business rows."""
    ro_id, dealer_id, _ = await _new_ro(deps, "missing")
    await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))
    before = await _business_state(deps, ro_id)
    again = await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))
    outcomes = {t["node"]: t["outcome"] for t in again.values["execution_trace"][-9:]}
    assert outcomes["warranty"] == outcomes["estimate"] == outcomes["risk"] == "cached"
    after = await _business_state(deps, ro_id)
    assert {k: v for k, v in after.items() if k != "audit"} == {k: v for k, v in before.items() if k != "audit"}


async def test_estimate_resume_rbac_then_owner_approves(deps: NodeDeps, saver: Any) -> None:
    ro_id, dealer_id, owner_id = await _new_ro(deps, "customer")
    await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))

    with pytest.raises(InvalidTransition):  # advisor has not sent the estimate yet
        await resume_estimate(
            deps, saver, Actor(owner_id, Role.VEHICLE_OWNER, None), ro_id, DecisionIn(decision="approve_all")
        )
    await _send_estimate(deps, ro_id, dealer_id)

    with pytest.raises(ForbiddenRole):
        await resume_estimate(
            deps, saver, Actor(uuid.uuid4(), Role.TECHNICIAN, dealer_id), ro_id, DecisionIn(decision="approve_all")
        )
    with pytest.raises(NotFound):  # someone else's vehicle
        await resume_estimate(
            deps, saver, Actor(uuid.uuid4(), Role.VEHICLE_OWNER, None), ro_id, DecisionIn(decision="approve_all")
        )
    with pytest.raises(NotFound):  # advisor at another dealer
        await resume_estimate(
            deps, saver, advisor(uuid.uuid4()), ro_id, DecisionIn(decision="approve_all", rationale="ok")
        )
    with pytest.raises(RationaleRequired):  # advisor must record a consent note
        await resume_estimate(deps, saver, advisor(dealer_id), ro_id, DecisionIn(decision="approve_all"))
    with pytest.raises(ValidationFailed):
        await resume_estimate(
            deps, saver, Actor(owner_id, Role.VEHICLE_OWNER, None), ro_id, DecisionIn(decision="sure")
        )
    assert await _status(deps, ro_id) == ROStatus.AWAITING_OWNER_APPROVAL  # still interrupted

    owner = Actor(owner_id, Role.VEHICLE_OWNER, None)
    decision = DecisionIn(decision="approve_all", decision_id="dec-owner-approve-1")
    done = await resume_estimate(deps, saver, owner, ro_id, decision)
    assert done.waiting_for is None and await _status(deps, ro_id) == ROStatus.APPROVED
    again = await resume_estimate(deps, saver, owner, ro_id, decision)  # duplicate resume → no-op
    assert again.waiting_for is None
    async with deps.sessionmaker() as s:
        decisions = list(await s.scalars(select(ReviewDecision).where(ReviewDecision.ro_id == ro_id)))
        assert (
            len(decisions) == 1 and decisions[0].actor_role == "vehicle_owner" and decisions[0].evidence_snapshot_hash
        )
        lines = list(
            await s.scalars(select(EstimateLine).where(EstimateLine.ro_id == ro_id, EstimateLine.kind != "tax"))
        )
        assert {ln.owner_decision for ln in lines} == {"approved"}
        hist = await s.scalar(
            select(ROStatusHistory).where(
                ROStatusHistory.ro_id == ro_id, ROStatusHistory.to_status == ROStatus.APPROVED
            )
        )
        assert hist is not None and hist.actor_role == "vehicle_owner"
        assert (
            await s.scalar(
                select(func.count()).select_from(Notification).where(Notification.payload["ro_ref"].astext != "")
            )
            > 0
        )


async def test_per_line_decline_all_lines_declines_ro(deps: NodeDeps, saver: Any) -> None:
    ro_id, dealer_id, owner_id = await _new_ro(deps, "customer")
    await run_ro_workflow(deps, saver, ro_id, advisor(dealer_id))
    await _send_estimate(deps, ro_id, dealer_id)
    lines = [{"code": "OP-BRK-PAD-FR", "decision": "declined"}, {"code": "VLX-BRK-PAD-TR", "decision": "declined"}]
    with pytest.raises(ValidationFailed):
        await resume_estimate(
            deps,
            saver,
            Actor(owner_id, Role.VEHICLE_OWNER, None),
            ro_id,
            DecisionIn(decision="per_line", line_decisions=[{"code": "NOT-A-LINE", "decision": "approved"}]),
        )
    await resume_estimate(
        deps,
        saver,
        Actor(owner_id, Role.VEHICLE_OWNER, None),
        ro_id,
        DecisionIn(decision="per_line", line_decisions=lines),
    )
    assert await _status(deps, ro_id) == ROStatus.DECLINED


async def test_claim_decision_after_process_restart(deps: NodeDeps, tmp_path: Any) -> None:
    async with postgres_checkpointer() as first_saver:
        ro_id, dealer_id, _ = await _new_ro(deps, "clean")
        result = await run_ro_workflow(deps, first_saver, ro_id, advisor(dealer_id))
        claim_id = uuid.UUID(result.values["warranty"]["claim_id"])
    # "restart": a brand-new checkpointer pool and freshly compiled graphs restore the interrupted claim thread
    async with postgres_checkpointer() as saver:
        admin = await _staff(deps, dealer_id, Role.WARRANTY_ADMIN)
        with pytest.raises(ForbiddenRole):
            await resume_claim(
                deps,
                saver,
                Actor(uuid.uuid4(), Role.ADMIN, None),
                claim_id,
                DecisionIn(decision="submit_to_oem", rationale="x"),
            )
        with pytest.raises(NotFound):
            await resume_claim(
                deps,
                saver,
                Actor(uuid.uuid4(), Role.WARRANTY_ADMIN, uuid.uuid4()),
                claim_id,
                DecisionIn(decision="submit_to_oem", rationale="x"),
            )
        with pytest.raises(RationaleRequired):
            await resume_claim(deps, saver, admin, claim_id, DecisionIn(decision="submit_to_oem"))

        from app.graph.nodes import record_decision as rd

        original = rd.DemoOemAdapter
        rd.DemoOemAdapter = lambda: DemoOemAdapter(tmp_path)  # type: ignore[assignment,misc]
        try:
            done = await resume_claim(
                deps,
                saver,
                admin,
                claim_id,
                DecisionIn(decision="submit_to_oem", rationale="All rules pass; documents complete."),
            )
        finally:
            rd.DemoOemAdapter = original  # type: ignore[misc]
        assert done.waiting_for is None
    async with deps.sessionmaker() as s:
        claim = await s.get(WarrantyClaim, claim_id)
        assert claim is not None and claim.status == ClaimStatus.SUBMITTED_TO_OEM
        assert claim.oem_ack and claim.oem_ack["adapter"] == "DEMO" and claim.oem_ack["status"] == "RECEIVED"
        assert (tmp_path / f"{claim.claim_ref}.json").exists()
        actions = list(
            await s.scalars(select(AuditLog.action).where(AuditLog.entity_id == claim_id).order_by(AuditLog.seq))
        )
        assert actions.count("warranty_claim.transition") == 3  # PREPARED → REVIEW_REQUIRED → SUBMITTED_TO_OEM
    assert SYSTEM_ACTOR.role == "system"
