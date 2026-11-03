"""Organization repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Organization repository."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Organization, db)

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Fetch organization by slug."""

        query = select(Organization).where(Organization.slug == slug)

        result = await self.db.execute(query)

        return result.scalar_one_or_none()
