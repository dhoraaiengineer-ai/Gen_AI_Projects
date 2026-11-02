"""Repair orders — read endpoints (docs/API_SPEC.md §3.6). State changes arrive in later tasks via transition()."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.service import to_status_out
from app.core.db import get_session
from app.core.errors import NotFound, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.graph.nodes.status import load_status
from app.models.enums import Role, ROStatus
from app.repositories.repair_orders import RepairOrderRepo
from app.schemas.chat import ROStatusOut
from app.schemas.common import Page, StatusEvent, masked_vin
from app.schemas.envelope import Envelope
from app.schemas.repair_orders import CheckInOut, ComplaintOut, DealerRef, RODetail, ROSummary, ROVehicle
from app.schemas.vehicle_context import CheckInIn, CheckInResult
from app.services import idempotency
from app.services.check_in import check_in

router = APIRouter(prefix="/api/v1/repair-orders", tags=["repair-orders"])

_READERS = require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR, Role.TECHNICIAN, Role.WARRANTY_ADMIN)


@router.get("", response_model=Envelope[Page[ROSummary]])
async def list_repair_orders(
    request: Request,
    status: ROStatus | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[ROSummary]]:
    rows = await RepairOrderRepo(session).list_scoped(
        actor, status=status.value if status else None, limit=limit, offset=offset
    )
    items = [
        ROSummary(
            id=ro.id,
            ro_ref=ro.ro_ref,
            status=ro.status,
            vehicle=ROVehicle(id=v.id, model=m.name, model_year=v.model_year, vin_masked=masked_vin(v.vin)),
            created_at=ro.created_at,
            updated_at=ro.updated_at,
        )
        for ro, v, m in rows
    ]
    nxt = str(offset + limit) if len(items) == limit else None
    return Envelope.ok(Page(items=items, next_cursor=nxt), get_request_id(request))


@router.get("/{ro_id}", response_model=Envelope[RODetail])
async def get_repair_order(
    ro_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[RODetail]:
    found = await RepairOrderRepo(session).detail(actor, ro_id)
    if found is None:
        raise NotFound()
    ro, vehicle, model, dealer, complaints, history = found
    check_in = (
        CheckInOut(
            odometer_in_km=ro.odometer_in_km,
            fuel_or_charge_level=ro.fuel_or_charge_level,
            damage_notes=ro.damage_notes,
        )
        if ro.odometer_in_km is not None
        else None
    )
    return Envelope.ok(
        RODetail(
            id=ro.id,
            ro_ref=ro.ro_ref,
            status=ro.status,
            dealer=DealerRef(id=dealer.id, name=dealer.name),
            vehicle=ROVehicle(
                id=vehicle.id, model=model.name, model_year=vehicle.model_year, vin_masked=masked_vin(vehicle.vin)
            ),
            complaints=[
                ComplaintOut(text=c.complaint_text, confirmed_by_advisor=c.confirmed_by_advisor) for c in complaints
            ],
            check_in=check_in,
            promised_ready_at=ro.promised_ready_at,
            timeline=[
                StatusEvent(
                    from_status=h.from_status,
                    to_status=h.to_status,
                    at=h.created_at,
                    actor_role=h.actor_role,
                    reason=h.reason,
                )
                for h in history
            ],
        ),
        get_request_id(request),
    )


@router.get("/{ro_id}/status", response_model=Envelope[ROStatusOut])
async def get_status(
    ro_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ROStatusOut]:
    """Reads only repair_orders / ro_status_history (+ claim). Deterministic phrasing; no ETA unless stored."""
    result = await load_status(session, actor, ro_id)
    if result is None:
        raise NotFound()
    return Envelope.ok(to_status_out(result, result.phrased), get_request_id(request))


@router.post("/{ro_id}/check-in", response_model=Envelope[CheckInResult])
async def check_in_ro(
    ro_id: uuid.UUID,
    body: CheckInIn,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=64),
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[CheckInResult]:
    route = f"POST /repair-orders/{ro_id}/check-in"
    payload = body.model_dump(mode="json")
    stored = await idempotency.replay(session, actor, idempotency_key, route, payload)
    if stored is not None:
        return Envelope.ok(CheckInResult.model_validate(stored | {"replayed": True}), get_request_id(request))
    if not idempotency_key.replace("-", "").isalnum():
        raise ValidationFailed("Idempotency-Key must be 8-64 characters [A-Za-z0-9-].")
    out = await check_in(session, actor, ro_id, body)
    await idempotency.remember(session, actor, idempotency_key, route, payload, out.model_dump(mode="json"))
    await session.commit()
    return Envelope.ok(out, get_request_id(request))
