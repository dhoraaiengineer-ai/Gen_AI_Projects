"""Base repository pattern for reusable database access."""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Reusable async repository base class."""

    def __init__(
        self,
        model: type[ModelType],
        db: AsyncSession,
    ) -> None:
        self.model = model
        self.db = db

    async def get_by_id(self, entity_id: str) -> ModelType | None:
        """Fetch entity by ID."""

        query = select(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]  # all ORM models define `id`

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(self, obj: ModelType) -> ModelType:
        """Create entity."""

        self.db.add(obj)

        await self.db.flush()
        await self.db.refresh(obj)

        return obj

    async def delete(self, obj: ModelType) -> None:
        """Delete entity."""

        await self.db.delete(obj)
