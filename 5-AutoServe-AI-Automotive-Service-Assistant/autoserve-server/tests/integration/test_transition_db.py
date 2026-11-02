"""transition() against the real DB: history + audit in one transaction, scope enforced, failures roll back."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.core.errors import ForbiddenRole, NotFound
from app.core.security import Actor
from app.models import AuditLog, Dealer, RepairOrder, ROStatusHistory, User
from app.models.enums import ROStatus

pytestmark = pytest.mark.integration


async def _advisor(email: str) -> Actor:
    async with get_sessionmaker()() as s:
        u = await s.scalar(select(User).where(User.email == email))
        assert u is not None
        return Actor(u.id, "service_advisor", u.dealer_id)


async def _booked_ro_at(dealer_code: str) -> uuid.UUID:
    async with get_sessionmaker()() as s:
        ro_id = await s.scalar(
            select(RepairOrder.id)
            .join(Dealer, Dealer.id == RepairOrder.dealer_id)
            .where(Dealer.code == dealer_code, RepairOrder.status == ROStatus.BOOKED)
        )
        assert ro_id is not None
        return ro_id


async def test_transition_writes_status_history_and_audit(seeded_db: str) -> None:
    from app.services.state_machine import transition

    actor = await _advisor("advisor.d1@autoserve.example.test")
    ro_id = await _booked_ro_at("VLX-D01")
    async with get_sessionmaker()() as s, s.begin():
        audit_before = await s.scalar(select(func.count()).select_from(AuditLog))
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None
        await transition(s, ro, ROStatus.CHECKED_IN, actor)
    async with get_sessionmaker()() as s:
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None and ro.status == ROStatus.CHECKED_IN
        last = await s.scalar(
            select(ROStatusHistory).where(ROStatusHistory.ro_id == ro_id).order_by(ROStatusHistory.created_at.desc())
        )
        assert last is not None and (last.from_status, last.to_status) == ("BOOKED", "CHECKED_IN")
        assert last.actor_role == "service_advisor"
        assert await s.scalar(select(func.count()).select_from(AuditLog)) == (audit_before or 0) + 1


async def test_other_dealer_staff_cannot_transition(seeded_db: str) -> None:
    from app.services.state_machine import transition

    outsider = await _advisor("advisor.d2@autoserve.example.test")
    async with get_sessionmaker()() as s:
        ro_id = await s.scalar(
            select(RepairOrder.id)
            .join(Dealer, Dealer.id == RepairOrder.dealer_id)
            .where(Dealer.code == "VLX-D01", RepairOrder.status == ROStatus.DIAGNOSING)
        )
    async with get_sessionmaker()() as s:
        with pytest.raises(NotFound):
            async with s.begin():
                ro = await s.get(RepairOrder, ro_id)
                assert ro is not None
                await transition(s, ro, ROStatus.CANCELLED, outsider, reason="not mine")
    async with get_sessionmaker()() as s:
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None and ro.status == ROStatus.DIAGNOSING  # unchanged


async def test_rejected_transition_rolls_back_everything(seeded_db: str) -> None:
    from app.services.state_machine import transition

    async with get_sessionmaker()() as s:
        tech = await s.scalar(select(User).where(User.email == "tech.d1@autoserve.example.test"))
        ro_id = await s.scalar(
            select(RepairOrder.id)
            .join(Dealer, Dealer.id == RepairOrder.dealer_id)
            .where(Dealer.code == "VLX-D01", RepairOrder.status == ROStatus.DIAGNOSING)
        )
        history_before = await s.scalar(select(func.count()).where(ROStatusHistory.ro_id == ro_id))
    assert tech is not None
    actor = Actor(tech.id, "technician", tech.dealer_id)
    async with get_sessionmaker()() as s:
        with pytest.raises(ForbiddenRole):  # technician may not cancel
            async with s.begin():
                ro = await s.get(RepairOrder, ro_id)
                assert ro is not None
                await transition(s, ro, ROStatus.CANCELLED, actor, reason="x")
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).where(ROStatusHistory.ro_id == ro_id)) == history_before


async def _ro_with_status(dealer_code: str, status: ROStatus) -> uuid.UUID:
    async with get_sessionmaker()() as s:
        ro_id = await s.scalar(
            select(RepairOrder.id)
            .join(Dealer, Dealer.id == RepairOrder.dealer_id)
            .where(Dealer.code == dealer_code, RepairOrder.status == status)
            .limit(1)
        )
        assert ro_id is not None
        return ro_id


async def _owner_actor_of(ro_id: uuid.UUID) -> Actor:
    from app.models import Vehicle

    async with get_sessionmaker()() as s:
        owner_id = await s.scalar(
            select(Vehicle.owner_id)
            .join(RepairOrder, RepairOrder.vehicle_id == Vehicle.id)
            .where(RepairOrder.id == ro_id)
        )
        return Actor(owner_id, "vehicle_owner", None)


async def test_owner_decides_own_estimate_but_not_someone_elses(seeded_db: str) -> None:
    from app.services.state_machine import transition

    ro_id = await _ro_with_status("VLX-D02", ROStatus.AWAITING_OWNER_APPROVAL)
    owner = await _owner_actor_of(ro_id)
    async with get_sessionmaker()() as s:
        stranger_id = await s.scalar(select(User.id).where(User.email == "owner.priya@example.test"))
    stranger = Actor(stranger_id, "vehicle_owner", None)
    assert stranger.user_id != owner.user_id

    async with get_sessionmaker()() as s:
        with pytest.raises(NotFound):
            async with s.begin():
                ro = await s.get(RepairOrder, ro_id)
                assert ro is not None
                await transition(s, ro, ROStatus.APPROVED, stranger)
    async with get_sessionmaker()() as s, s.begin():
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None
        await transition(s, ro, ROStatus.APPROVED, owner)
    async with get_sessionmaker()() as s:
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None and ro.status == ROStatus.APPROVED


async def test_admin_cannot_transition_anything(seeded_db: str) -> None:
    from app.services.state_machine import transition

    async with get_sessionmaker()() as s:
        admin_id = await s.scalar(select(User.id).where(User.email == "admin@autoserve.example.test"))
    ro_id = await _ro_with_status("VLX-D01", ROStatus.INFO_PENDING)
    async with get_sessionmaker()() as s:
        with pytest.raises(ForbiddenRole):
            async with s.begin():
                ro = await s.get(RepairOrder, ro_id)
                assert ro is not None
                await transition(s, ro, ROStatus.DIAGNOSING, Actor(admin_id, "admin", None))


async def test_unknown_entity_is_not_found(seeded_db: str) -> None:
    from app.core.security import SYSTEM_ACTOR
    from app.services.state_machine import transition

    ghost = RepairOrder(id=uuid.uuid4())
    async with get_sessionmaker()() as s:
        with pytest.raises(NotFound):
            async with s.begin():
                await transition(s, ghost, ROStatus.BOOKED, SYSTEM_ACTOR)


async def test_system_moves_claim_and_writes_claim_history(seeded_db: str) -> None:
    from app.core.security import SYSTEM_ACTOR
    from app.models import WarrantyClaim, WarrantyStatusHistory
    from app.services.state_machine import transition

    ro_id = await _ro_with_status("VLX-D01", ROStatus.IN_REPAIR)
    async with get_sessionmaker()() as s, s.begin():
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None
        claim = WarrantyClaim(ro_id=ro.id, dealer_id=ro.dealer_id, component_group="test_group")
        s.add(claim)
        await s.flush()
        await transition(s, claim, "PREPARED", SYSTEM_ACTOR)
        claim_id = claim.id
    async with get_sessionmaker()() as s:
        claim = await s.get(WarrantyClaim, claim_id)
        assert claim is not None and claim.status == "PREPARED" and claim.claim_ref.startswith("WC-")
        hist = await s.scalar(select(WarrantyStatusHistory).where(WarrantyStatusHistory.claim_id == claim_id))
        assert hist is not None and (hist.from_status, hist.to_status, hist.actor_role) == (
            "DRAFT",
            "PREPARED",
            "system",
        )


async def test_cancel_stores_reason(seeded_db: str) -> None:
    from app.services.state_machine import transition

    actor = await _advisor("advisor.d1@autoserve.example.test")
    ro_id = await _ro_with_status("VLX-D01", ROStatus.CHECKED_IN)
    async with get_sessionmaker()() as s, s.begin():
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None
        await transition(s, ro, ROStatus.CANCELLED, actor, reason="Owner sold the vehicle (SYNTHETIC)")
    async with get_sessionmaker()() as s:
        ro = await s.get(RepairOrder, ro_id)
        assert ro is not None and ro.status == ROStatus.CANCELLED
        assert ro.cancel_reason == "Owner sold the vehicle (SYNTHETIC)"
