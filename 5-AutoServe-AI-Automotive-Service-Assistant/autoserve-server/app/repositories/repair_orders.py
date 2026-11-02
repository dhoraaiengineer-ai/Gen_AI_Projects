"""Actor-scoped repair-order access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Actor
from app.models import Dealer, RepairOrder, ROComplaint, ROStatusHistory, Vehicle, VehicleModel
from app.repositories.scope import repair_order_scope


class RepairOrderRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_scoped(
        self, actor: Actor, status: str | None = None, limit: int = 25, offset: int = 0
    ) -> list[tuple[RepairOrder, Vehicle, VehicleModel]]:
        stmt = (
            select(RepairOrder, Vehicle, VehicleModel)
            .join(Vehicle, Vehicle.id == RepairOrder.vehicle_id)
            .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
            .where(repair_order_scope(actor))
            .order_by(RepairOrder.created_at.desc(), RepairOrder.id)
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(RepairOrder.status == status)
        return [(ro, v, m) for ro, v, m in (await self.session.execute(stmt)).all()]

    async def get(self, actor: Actor, ro_id: uuid.UUID) -> RepairOrder | None:
        return await self.session.scalar(select(RepairOrder).where(RepairOrder.id == ro_id, repair_order_scope(actor)))

    async def get_by_ref(self, actor: Actor, ro_ref: str) -> RepairOrder | None:
        stmt = select(RepairOrder).where(RepairOrder.ro_ref == ro_ref.upper(), repair_order_scope(actor))
        return await self.session.scalar(stmt)

    async def open_for_owner(self, actor: Actor) -> list[RepairOrder]:
        stmt = (
            select(RepairOrder)
            .where(repair_order_scope(actor), RepairOrder.status.not_in(("CLOSED", "CANCELLED")))
            .order_by(RepairOrder.created_at.desc())
        )
        return list(await self.session.scalars(stmt))

    async def detail(
        self, actor: Actor, ro_id: uuid.UUID
    ) -> tuple[RepairOrder, Vehicle, VehicleModel, Dealer, list[ROComplaint], list[ROStatusHistory]] | None:
        stmt = (
            select(RepairOrder, Vehicle, VehicleModel, Dealer)
            .join(Vehicle, Vehicle.id == RepairOrder.vehicle_id)
            .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
            .join(Dealer, Dealer.id == RepairOrder.dealer_id)
            .where(RepairOrder.id == ro_id, repair_order_scope(actor))
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        ro, vehicle, model, dealer = row
        complaints = list(
            await self.session.scalars(
                select(ROComplaint).where(ROComplaint.ro_id == ro.id).order_by(ROComplaint.created_at)
            )
        )
        history = list(
            await self.session.scalars(
                select(ROStatusHistory)
                .where(ROStatusHistory.ro_id == ro.id)
                .order_by(ROStatusHistory.created_at, ROStatusHistory.id)
            )
        )
        return ro, vehicle, model, dealer, complaints, history
