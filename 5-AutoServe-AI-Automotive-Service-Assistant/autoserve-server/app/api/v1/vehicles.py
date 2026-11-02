"""Vehicles (docs/API_SPEC.md §3.4). Owner: own vehicles; staff: vehicles with an RO at their dealer."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import InvalidVin, NotFound
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.graph.nodes.vehicle_context import build_vehicle_context
from app.models import RepairOrder
from app.models.enums import Role
from app.rag.answer import Citation
from app.repositories.repair_orders import RepairOrderRepo
from app.repositories.vehicles import VehicleRepo
from app.schemas.chat import RecallNotice
from app.schemas.common import Page, masked_plate, masked_vin
from app.schemas.envelope import Envelope
from app.schemas.vehicle_context import VehicleContextOut
from app.schemas.vehicles import DecodedVinOut, VehicleDetail, VehicleSummary
from app.services.recalls import open_recalls_for
from app.services.vin import decode_vin

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

_READERS = require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR, Role.TECHNICIAN, Role.WARRANTY_ADMIN)


@router.get("", response_model=Envelope[Page[VehicleSummary]])
async def list_vehicles(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[VehicleSummary]]:
    rows = await VehicleRepo(session).list_scoped(actor, limit=limit, offset=offset)
    items = [
        VehicleSummary(
            id=v.id,
            vin_masked=masked_vin(v.vin),
            model=m.name,
            model_year=v.model_year,
            plate_masked=masked_plate(v.plate_number),
            last_odometer_km=v.last_odometer_km,
        )
        for v, m in rows
    ]
    nxt = str(offset + limit) if len(items) == limit else None
    return Envelope.ok(Page(items=items, next_cursor=nxt), get_request_id(request))


@router.get("/{vehicle_id}", response_model=Envelope[VehicleDetail])
async def get_vehicle(
    vehicle_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[VehicleDetail]:
    repo = VehicleRepo(session)
    found = await repo.get(actor, vehicle_id)
    if found is None:
        raise NotFound()
    vehicle, model = found
    try:
        d = decode_vin(vehicle.vin, await repo.catalogue())
        decoded: DecodedVinOut | None = DecodedVinOut(
            wmi=d.wmi, model=d.model, model_year=d.model_year, plant=d.plant, serial=d.serial
        )
    except InvalidVin:
        decoded = None
    return Envelope.ok(
        VehicleDetail(
            id=vehicle.id,
            vin=vehicle.vin,
            decoded=decoded,
            model=model.name,
            model_year=vehicle.model_year,
            in_service_date=vehicle.in_service_date,
            last_odometer_km=vehicle.last_odometer_km,
            plate_number=vehicle.plate_number,
        ),
        get_request_id(request),
    )


@router.get("/{vehicle_id}/recalls", response_model=Envelope[Page[RecallNotice]])
async def vehicle_recalls(
    vehicle_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[RecallNotice]]:
    found = await VehicleRepo(session).get(actor, vehicle_id)
    if found is None:
        raise NotFound()
    items = []
    for r in await open_recalls_for(session, found[0]):
        notice = None
        if r.notice_chunk_id and r.notice_quote:
            notice = Citation(
                chunk_id=r.notice_chunk_id,
                source_file=r.notice_source_file or "",
                page=r.notice_page or 1,
                section_id=r.notice_section_id or "",
                section_title=r.title,
                quote=r.notice_quote,
            )
        items.append(
            RecallNotice(campaign_code=r.campaign_code, title=r.title, component_group=r.component_group, notice=notice)
        )
    return Envelope.ok(Page(items=items), get_request_id(request))


@router.get("/{vehicle_id}/context", response_model=Envelope[VehicleContextOut])
async def vehicle_context(
    vehicle_id: uuid.UUID,
    request: Request,
    ro_id: uuid.UUID | None = None,
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR, Role.TECHNICIAN, Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[VehicleContextOut]:
    found = await VehicleRepo(session).get(actor, vehicle_id)
    if found is None:
        raise NotFound()
    ro: RepairOrder | None = None
    if ro_id is not None:
        ro = await RepairOrderRepo(session).get(actor, ro_id)
        if ro is None or ro.vehicle_id != vehicle_id:
            raise NotFound()
    vehicle, model = found
    return Envelope.ok(await build_vehicle_context(session, vehicle, model, ro), get_request_id(request))
