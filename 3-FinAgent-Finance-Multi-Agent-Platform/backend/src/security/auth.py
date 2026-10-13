"""Supabase JWT authentication and the FastAPI auth dependencies.

* Tokens are verified against the project's JWKS — **ES256/RS256 only**, ``aud=authenticated``,
  issuer ``<SUPABASE_URL>/auth/v1``, expiry enforced.
* The role comes **only** from ``app_metadata.app_role`` (users cannot edit app_metadata); a
  missing/unknown role means ``viewer`` (least privilege).
* The tenant comes **only** from ``app_metadata.tenant_id``; a token without one is rejected.
* ``require_user`` sets the tenant scope for the request (ADR-026); every route declares it or
  ``require_role(...)`` / ``require_permission(...)`` (enforced by the architecture test).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from jwt import PyJWKClient

from src.core.context import user_id_var
from src.core.domain import Role
from src.core.errors import Forbidden, Unauthorized
from src.core.metrics import AUTH_FAILURES
from src.core.tenancy import reset_tenant, set_tenant
from src.security.rbac import has_permission

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = ["ES256", "RS256"]


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    role: Role
    tenant_id: str

    def can(self, permission: str) -> bool:
        return has_permission(self.role, permission)


CLOCK_SKEW_SECONDS = 30  # tolerate small clock differences (iat/nbf/exp) between hosts


class JwtVerifier:
    def __init__(self, jwks_url: str, issuer: str, audience: str = "authenticated") -> None:
        self._jwks = PyJWKClient(jwks_url, cache_keys=True, lifespan=600, timeout=10)
        self.issuer = issuer
        self.audience = audience

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in ALLOWED_ALGORITHMS:
                raise Unauthorized("unsupported token algorithm")
            key = await asyncio.to_thread(self._jwks.get_signing_key_from_jwt, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except Unauthorized:
            AUTH_FAILURES.labels(reason="algorithm").inc()
            raise
        except jwt.ExpiredSignatureError as exc:
            AUTH_FAILURES.labels(reason="expired").inc()
            raise Unauthorized("token expired") from exc
        except (jwt.PyJWTError, ValueError) as exc:
            AUTH_FAILURES.labels(reason="invalid").inc()
            raise Unauthorized("invalid token") from exc
        return principal_from_claims(claims)


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    app_meta = claims.get("app_metadata") or {}
    try:
        role = Role(str(app_meta.get("app_role", Role.VIEWER.value)))
    except ValueError:
        role = Role.VIEWER
    tenant = app_meta.get("tenant_id")
    try:
        tenant_id = str(uuid.UUID(str(tenant)))
    except (ValueError, TypeError) as exc:
        AUTH_FAILURES.labels(reason="no_tenant").inc()
        raise Forbidden("account is not assigned to a tenant") from exc
    return Principal(
        user_id=str(claims["sub"]), email=claims.get("email"), role=role, tenant_id=tenant_id
    )


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        AUTH_FAILURES.labels(reason="missing").inc()
        raise Unauthorized("missing bearer token")
    return token.strip()


async def require_user(request: Request) -> AsyncIterator[Principal]:
    """Authenticate the caller and scope the request to their tenant."""
    verifier: JwtVerifier | None = getattr(request.app.state.container, "jwt_verifier", None)
    if verifier is None:
        raise Unauthorized("authentication is not configured")
    principal = await verifier.verify(_bearer(request))
    tenant_token = set_tenant(principal.tenant_id)
    user_token = user_id_var.set(principal.user_id)
    try:
        yield principal
    finally:
        user_id_var.reset(user_token)
        reset_tenant(tenant_token)


CurrentUser = Annotated[Principal, Depends(require_user)]


def require_role(*roles: Role) -> Callable[..., Any]:
    """Dependency: the caller must have one of ``roles``."""

    async def dependency(principal: CurrentUser) -> Principal:
        if principal.role not in roles:
            raise Forbidden("your role cannot use this endpoint")
        return principal

    dependency.required_role = roles  # type: ignore[attr-defined]  # marker for the architecture test
    return dependency


def require_permission(*permissions: str) -> Callable[..., Any]:
    """Dependency: the caller's role must grant one of ``permissions`` (src/security/rbac.py)."""

    async def dependency(principal: CurrentUser) -> Principal:
        if not any(principal.can(p) for p in permissions):
            raise Forbidden(f"your role lacks the {' or '.join(map(repr, permissions))} permission")
        return principal

    dependency.required_role = permissions  # type: ignore[attr-defined]
    return dependency
