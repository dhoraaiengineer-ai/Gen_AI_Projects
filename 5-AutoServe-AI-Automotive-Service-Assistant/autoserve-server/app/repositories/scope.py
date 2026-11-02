"""Row-level scope predicates (CLAUDE.md §3). Every RO/vehicle/claim query must apply one of these.

Subqueries use aliased tables so they never auto-correlate with a table the outer query already joins.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, exists, false, select
from sqlalchemy.orm import aliased

from app.core.security import Actor
from app.models import RepairOrder, Vehicle


def vehicle_scope(actor: Actor) -> ColumnElement[bool]:
    """Owner: own vehicles. Staff: vehicles with an RO at the actor's dealer. Anyone else: nothing."""
    if actor.is_owner:
        return Vehicle.owner_id == actor.user_id
    if actor.is_staff and actor.dealer_id is not None:
        ro = aliased(RepairOrder)
        return exists(select(ro.id).where(and_(ro.vehicle_id == Vehicle.id, ro.dealer_id == actor.dealer_id)))
    return false()


def repair_order_scope(actor: Actor) -> ColumnElement[bool]:
    """Owner: ROs of own vehicles. Staff: ROs at the actor's dealer. Anyone else: nothing."""
    if actor.is_owner:
        v = aliased(Vehicle)
        return exists(select(v.id).where(and_(v.id == RepairOrder.vehicle_id, v.owner_id == actor.user_id)))
    if actor.is_staff and actor.dealer_id is not None:
        return RepairOrder.dealer_id == actor.dealer_id
    return false()
