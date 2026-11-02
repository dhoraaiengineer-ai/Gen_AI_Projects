"""Actor-scoped vehicle access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Actor
from app.models import Vehicle, VehicleModel
from app.repositories.scope import vehicle_scope
from app.services.vin import ModelSpec


class VehicleRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_scoped(self, actor: Actor, limit: int = 25, offset: int = 0) -> list[tuple[Vehicle, VehicleModel]]:
        stmt = (
            select(Vehicle, VehicleModel)
            .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
            .where(vehicle_scope(actor), Vehicle.deleted_at.is_(None))
            .order_by(Vehicle.created_at, Vehicle.id)
            .limit(limit)
            .offset(offset)
        )
        return [(v, m) for v, m in (await self.session.execute(stmt)).all()]

    async def get(self, actor: Actor, vehicle_id: uuid.UUID) -> tuple[Vehicle, VehicleModel] | None:
        stmt = (
            select(Vehicle, VehicleModel)
            .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
            .where(Vehicle.id == vehicle_id, vehicle_scope(actor), Vehicle.deleted_at.is_(None))
        )
        row = (await self.session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def catalogue(self) -> list[ModelSpec]:
        """Model catalogue is reference data (not owner/dealer data), so it is not actor-scoped."""
        models = await self.session.scalars(select(VehicleModel))
        return [ModelSpec(m.name, m.vds_code, m.model_year_from, m.model_year_to, tuple(m.plant_codes)) for m in models]
