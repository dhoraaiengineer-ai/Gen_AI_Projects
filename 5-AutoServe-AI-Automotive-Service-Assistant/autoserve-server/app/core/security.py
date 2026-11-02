"""Authentication (DEMO JWT locally, OIDC JWKS in prod) and role-based access (rules/70, CLAUDE.md §3)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ForbiddenRole, RateLimited, Unauthenticated
from app.models.enums import STAFF_ROLES, Role

# ── Passwords (DEMO login only; stdlib scrypt) ──────────────────────────────────────────────────────────
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return "$".join(["scrypt", str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P), _b64(salt), _b64(digest)])


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, _unb64(digest))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ── Actor ───────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Actor:
    user_id: uuid.UUID | None
    role: str  # a Role value, or "system"
    dealer_id: uuid.UUID | None

    @property
    def is_system(self) -> bool:
        return self.role == "system"

    @property
    def is_owner(self) -> bool:
        return self.role == Role.VEHICLE_OWNER

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES


SYSTEM_ACTOR = Actor(user_id=None, role="system", dealer_id=None)


# ── Tokens ──────────────────────────────────────────────────────────────────────────────────────────────
def create_access_token(user_id: uuid.UUID, role: str, settings: Settings) -> tuple[str, int]:
    if settings.auth_mode != "demo" or settings.jwt_secret is None:
        raise Unauthenticated("DEMO login is not enabled.")
    now = datetime.now(UTC)
    ttl = timedelta(minutes=settings.jwt_ttl_minutes)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    return token, int(ttl.total_seconds())


_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify signature, exp, iss, aud. Algorithm is pinned per mode; 'none' is never accepted."""
    try:
        if settings.auth_mode == "demo":
            if settings.jwt_secret is None:
                raise Unauthenticated()
            return jwt.decode(
                token,
                settings.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        # PROD (OIDC / Cognito) — configured in P5; not exercised by the local demo.
        if not (settings.oidc_jwks_url and settings.oidc_issuer and settings.oidc_audience):
            raise Unauthenticated()
        client = _jwks_clients.setdefault(settings.oidc_jwks_url, jwt.PyJWKClient(settings.oidc_jwks_url))
        key = client.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise Unauthenticated() from exc


_bearer = HTTPBearer(auto_error=False)


async def current_actor(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Actor:
    """Resolve the actor from the token, then load role/dealer from the DB (token claims are not trusted for scope)."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthenticated()
    settings = get_settings()
    claims = decode_token(creds.credentials, settings)
    from app.repositories.users import UserRepo  # local import: avoid cycle

    repo = UserRepo(session)
    if settings.auth_mode == "demo":
        try:
            user = await repo.get_active(uuid.UUID(str(claims["sub"])))
        except ValueError as exc:
            raise Unauthenticated() from exc
    else:
        user = await repo.get_by_oidc_sub(str(claims["sub"]))
    if user is None:
        raise Unauthenticated()
    return Actor(user_id=user.id, role=user.role.name, dealer_id=user.dealer_id)


def require_role(*roles: Role) -> Callable[..., Awaitable[Actor]]:
    allowed = frozenset(r.value for r in roles)

    async def _dep(actor: Actor = Depends(current_actor)) -> Actor:
        if actor.role not in allowed:
            raise ForbiddenRole()
        return actor

    return _dep


# ── Login rate limiting (in-memory, per client IP; replace with Redis/WAF in prod) ─────────────────────
class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_s: float = 60.0) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_s:
            hits.popleft()
        if len(hits) >= limit:
            raise RateLimited()
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


login_limiter = SlidingWindowLimiter()


async def login_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    login_limiter.check(f"login:{client}", get_settings().login_rate_limit_per_minute)
