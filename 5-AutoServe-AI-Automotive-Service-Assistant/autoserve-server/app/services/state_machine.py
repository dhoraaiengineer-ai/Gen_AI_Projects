"""The ONLY place RO / warranty-claim statuses change (CLAUDE.md §6, docs/LLD.md §3).

Transition tables are data. `transition()` validates edge + role + rationale, then writes the status,
the *_status_history row, and the audit event in the caller's DB transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenRole, InvalidTransition, NotFound, RationaleRequired
from app.core.security import Actor
from app.models import RepairOrder, ROStatusHistory, Vehicle, WarrantyClaim, WarrantyStatusHistory
from app.models.enums import ClaimStatus as C
from app.models.enums import ROStatus as R
from app.services.audit import AuditService

Machine = Literal["repair_order", "warranty_claim"]

OWNER, ADVISOR, TECH, WADMIN, SYSTEM = "vehicle_owner", "service_advisor", "technician", "warranty_admin", "system"


@dataclass(frozen=True)
class Edge:
    actors: frozenset[str]
    reason_required: bool = False
    note_required_for: frozenset[str] = frozenset()  # roles that must give a note (e.g. advisor recording consent)


def _e(*actors: str, reason: bool = False, note_for: tuple[str, ...] = ()) -> Edge:
    return Edge(frozenset(actors), reason, frozenset(note_for))


RO_TERMINAL = frozenset({R.CLOSED, R.CANCELLED})
CLAIM_TERMINAL = frozenset({C.OEM_ACCEPTED, C.OEM_REJECTED, C.REJECTED_BY_DEALER})

RO_TRANSITIONS: dict[tuple[str, str], Edge] = {
    (R.DRAFT, R.BOOKED): _e(OWNER, ADVISOR),  # RO-T01
    (R.BOOKED, R.CHECKED_IN): _e(ADVISOR),  # RO-T02
    (R.CHECKED_IN, R.DIAGNOSING): _e(TECH, ADVISOR),  # RO-T03
    (R.DIAGNOSING, R.INFO_PENDING): _e(SYSTEM, ADVISOR),  # RO-T04
    (R.INFO_PENDING, R.DIAGNOSING): _e(SYSTEM, ADVISOR),  # RO-T05
    (R.DIAGNOSING, R.ESTIMATE_READY): _e(SYSTEM),  # RO-T06 (precondition: estimable — enforced by caller, P3-5)
    (R.ESTIMATE_READY, R.AWAITING_OWNER_APPROVAL): _e(ADVISOR),  # RO-T07
    (R.AWAITING_OWNER_APPROVAL, R.APPROVED): _e(OWNER, ADVISOR, note_for=(ADVISOR,)),  # RO-T08
    (R.AWAITING_OWNER_APPROVAL, R.DECLINED): _e(OWNER, ADVISOR, note_for=(ADVISOR,)),  # RO-T09
    (R.APPROVED, R.IN_REPAIR): _e(ADVISOR, TECH),  # RO-T10
    (R.IN_REPAIR, R.QUALITY_CHECK): _e(TECH),  # RO-T11
    (R.QUALITY_CHECK, R.READY_FOR_PICKUP): _e(ADVISOR),  # RO-T12
    (R.DECLINED, R.READY_FOR_PICKUP): _e(ADVISOR),  # RO-T13
    (R.READY_FOR_PICKUP, R.CLOSED): _e(ADVISOR),  # RO-T14
}
# RO-T15: any non-terminal → CANCELLED (advisor, reason required)
for _s in R:
    if _s not in RO_TERMINAL:
        RO_TRANSITIONS[(_s, R.CANCELLED)] = _e(ADVISOR, reason=True)

CLAIM_TRANSITIONS: dict[tuple[str, str], Edge] = {
    (C.DRAFT, C.PREPARED): _e(SYSTEM),  # WC-T01
    (C.PREPARED, C.WARRANTY_REVIEW_REQUIRED): _e(SYSTEM),  # WC-T02
    (C.WARRANTY_REVIEW_REQUIRED, C.SUBMITTED_TO_OEM): _e(WADMIN, reason=True),  # WC-T03
    (C.WARRANTY_REVIEW_REQUIRED, C.RETURNED_FOR_INFO): _e(WADMIN, reason=True),  # WC-T04
    (C.WARRANTY_REVIEW_REQUIRED, C.REJECTED_BY_DEALER): _e(WADMIN, reason=True),  # WC-T05
    (C.RETURNED_FOR_INFO, C.PREPARED): _e(SYSTEM, ADVISOR),  # WC-T06
    (C.SUBMITTED_TO_OEM, C.OEM_ACCEPTED): _e(SYSTEM),  # WC-T07 (DEMO OEM adapter)
    (C.SUBMITTED_TO_OEM, C.OEM_REJECTED): _e(SYSTEM),  # WC-T08 (DEMO OEM adapter)
}

TABLES: dict[Machine, dict[tuple[str, str], Edge]] = {
    "repair_order": RO_TRANSITIONS,
    "warranty_claim": CLAIM_TRANSITIONS,
}


def check_transition(
    machine: Machine, from_status: str, to_status: str, actor_role: str, reason: str | None, note: str | None
) -> Edge:
    """Pure validation. Raises InvalidTransition / ForbiddenRole / RationaleRequired."""
    edge = TABLES[machine].get((from_status, to_status))
    if edge is None:
        raise InvalidTransition(details={"from": from_status, "to": to_status})
    if actor_role not in edge.actors:
        raise ForbiddenRole()
    if edge.reason_required and not (reason and reason.strip()):
        raise RationaleRequired()
    if actor_role in edge.note_required_for and not (note and note.strip()):
        raise RationaleRequired("A consent note is required when recording the owner's decision.")
    return edge


async def _assert_in_scope(session: AsyncSession, actor: Actor, dealer_id: object, vehicle_id: object) -> None:
    """Defence in depth: even if a caller skipped the repository, out-of-scope actors cannot transition."""
    if actor.is_system:
        return
    if actor.is_staff:
        if actor.dealer_id != dealer_id:
            raise NotFound()
        return
    if actor.is_owner:
        owner_id = await session.scalar(select(Vehicle.owner_id).where(Vehicle.id == vehicle_id))
        if owner_id != actor.user_id:
            raise NotFound()
        return
    raise ForbiddenRole()


async def transition(
    session: AsyncSession,
    entity: RepairOrder | WarrantyClaim,
    to_status: str,
    actor: Actor,
    *,
    reason: str | None = None,
    note: str | None = None,
) -> None:
    """Validate and apply one status change + history + audit. Runs inside the caller's transaction."""
    machine: Machine = "repair_order" if isinstance(entity, RepairOrder) else "warranty_claim"
    locked: RepairOrder | WarrantyClaim | None
    if isinstance(entity, RepairOrder):
        locked = await session.scalar(select(RepairOrder).where(RepairOrder.id == entity.id).with_for_update())
    else:
        locked = await session.scalar(select(WarrantyClaim).where(WarrantyClaim.id == entity.id).with_for_update())
    if locked is None:
        raise NotFound()

    if isinstance(locked, RepairOrder):
        await _assert_in_scope(session, actor, locked.dealer_id, locked.vehicle_id)
    else:  # claim scope follows its parent RO (FK guarantees the RO exists)
        vehicle_id = await session.scalar(select(RepairOrder.vehicle_id).where(RepairOrder.id == locked.ro_id))
        await _assert_in_scope(session, actor, locked.dealer_id, vehicle_id)

    from_status = locked.status
    check_transition(machine, from_status, to_status, actor.role, reason, note)

    locked.status = to_status
    history_reason = reason or note
    if isinstance(locked, RepairOrder):
        if to_status == R.CANCELLED:
            locked.cancel_reason = reason
        session.add(
            ROStatusHistory(
                ro_id=locked.id,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor.user_id,
                actor_role=actor.role,
                reason=history_reason,
            )
        )
    else:
        session.add(
            WarrantyStatusHistory(
                claim_id=locked.id,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor.user_id,
                actor_role=actor.role,
                reason=history_reason,
            )
        )
    await session.flush()
    await AuditService(session).record(
        actor,
        action=f"{machine}.transition",
        entity_type=machine,
        entity_id=locked.id,
        payload={"from": from_status, "to": to_status, "reason": history_reason},
    )
