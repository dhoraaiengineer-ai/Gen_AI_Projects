"""Base service layer utilities."""

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    """Base application service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
