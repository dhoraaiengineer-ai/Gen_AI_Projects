"""DEMO login + current user (docs/API_SPEC.md §3.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import Unauthenticated
from app.core.middleware import get_request_id
from app.core.security import Actor, create_access_token, current_actor, login_rate_limit, verify_password
from app.models import Dealer
from app.repositories.users import UserRepo
from app.schemas.auth import LoginIn, Me, TokenOut
from app.schemas.envelope import Envelope
from app.services.audit import AuditService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_BAD_LOGIN = "Invalid email or password."  # uniform message — no account enumeration


async def _me(session: AsyncSession, user_id: object) -> Me:
    user = await UserRepo(session).get_active(user_id)  # type: ignore[arg-type]
    if user is None:
        raise Unauthenticated()
    dealer = await session.get(Dealer, user.dealer_id) if user.dealer_id else None
    return Me(
        id=user.id,
        display_name=user.display_name,
        role=user.role.name,
        dealer_id=user.dealer_id,
        dealer_name=dealer.name if dealer else None,
    )


@router.post("/login", response_model=Envelope[TokenOut], dependencies=[Depends(login_rate_limit)])
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)) -> Envelope[TokenOut]:
    settings = get_settings()
    if settings.auth_mode != "demo":
        raise Unauthenticated("Use the organisation sign-in.")
    user = await UserRepo(session).get_by_email(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise Unauthenticated(_BAD_LOGIN)
    token, expires_in = create_access_token(user.id, user.role.name, settings)
    actor = Actor(user_id=user.id, role=user.role.name, dealer_id=user.dealer_id)
    await AuditService(session).record(actor, "auth.login", "user", user.id, {"mode": "demo"})
    await session.commit()
    return Envelope.ok(
        TokenOut(access_token=token, expires_in=expires_in, user=await _me(session, user.id)), get_request_id(request)
    )


@router.get("/me", response_model=Envelope[Me])
async def me(
    request: Request, actor: Actor = Depends(current_actor), session: AsyncSession = Depends(get_session)
) -> Envelope[Me]:
    return Envelope.ok(await _me(session, actor.user_id), get_request_id(request))
