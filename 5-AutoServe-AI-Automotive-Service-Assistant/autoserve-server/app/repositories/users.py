"""User lookups. Auth-path methods are not actor-scoped (they establish the actor); admin methods require admin."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenRole, ValidationFailed
from app.core.security import Actor, hash_password
from app.models import Dealer, RoleRow, User
from app.models.enums import STAFF_ROLES, Role


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, user_id: uuid.UUID) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.strip().lower(), User.deleted_at.is_(None))
        return await self.session.scalar(stmt)

    async def get_by_oidc_sub(self, sub: str) -> User | None:
        return await self.session.scalar(select(User).where(User.oidc_sub == sub, User.deleted_at.is_(None)))

    # ── admin ──
    async def list_all(self, actor: Actor) -> list[User]:
        _require_admin(actor)
        return list(await self.session.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.email)))

    async def create(
        self,
        actor: Actor,
        *,
        email: str,
        display_name: str,
        role: Role,
        dealer_id: uuid.UUID | None,
        password: str | None,
    ) -> User:
        _require_admin(actor)
        if (role in STAFF_ROLES) != (dealer_id is not None):
            raise ValidationFailed("Staff roles need exactly one dealer; other roles must have none.")
        if dealer_id is not None and await self.session.get(Dealer, dealer_id) is None:
            raise ValidationFailed("Unknown dealer.")
        if await self.get_by_email(email) is not None:
            raise ValidationFailed("A user with this email already exists.")
        role_row = await self.session.scalar(select(RoleRow).where(RoleRow.name == role.value))
        if role_row is None:
            raise ValidationFailed("Unknown role.")
        user = User(
            email=email.strip().lower(),
            display_name=display_name,
            role_id=role_row.id,
            dealer_id=dealer_id,
            password_hash=hash_password(password) if password else None,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["role"])
        return user


def _require_admin(actor: Actor) -> None:
    if actor.role != Role.ADMIN:
        raise ForbiddenRole()
