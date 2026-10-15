"""Supabase JWT verification against JWKS. Asymmetric algorithms only; roles only from app_metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = ("ES256", "RS256")
ROLE_RANK = {"user": 0, "clinician": 1, "admin": 2}


class AuthError(Exception):
    """Token missing, invalid, expired, or insufficient role."""


class SigningKeyResolver(Protocol):
    def get_signing_key(self, token: str) -> Any: ...


class JwksKeyResolver:
    """Fetches and caches the Supabase JWKS (network); used only in production wiring."""

    def __init__(self, jwks_url: str, cache_seconds: int = 600) -> None:
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=cache_seconds, timeout=5)

    def get_signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    roles: frozenset[str] = field(default_factory=lambda: frozenset({"user"}))

    @property
    def top_role(self) -> str:
        return max(self.roles, key=lambda r: ROLE_RANK.get(r, -1))

    def has_role(self, required: str) -> bool:
        return ROLE_RANK.get(self.top_role, -1) >= ROLE_RANK[required]


def roles_from_claims(claims: dict[str, Any]) -> frozenset[str]:
    """Read roles from app_metadata only. The top-level `role` claim (e.g. "authenticated") is ignored."""
    meta = claims.get("app_metadata") or {}
    raw: list[Any] = []
    if isinstance(meta.get("roles"), list):
        raw.extend(meta["roles"])
    if isinstance(meta.get("role"), str):
        raw.append(meta["role"])
    roles = {r for r in raw if isinstance(r, str) and r in ROLE_RANK}
    return frozenset(roles or {"user"})


class TokenVerifier:
    def __init__(
        self, resolver: SigningKeyResolver, audience: str, issuer: str | None, leeway_seconds: int = 30
    ) -> None:
        self._resolver = resolver
        self._audience = audience
        self._issuer = issuer
        # Small clock-skew allowance: a token issued "now" by Supabase must not be rejected as
        # not-yet-valid (iat/nbf) because this machine's clock is a few seconds behind.
        self._leeway = leeway_seconds

    def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthError("malformed token") from exc
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            # Rejects HS256 (shared secret) and "none" before any key lookup.
            raise AuthError("unsupported token algorithm")
        try:
            key = self._resolver.get_signing_key(token)
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud"]},
                leeway=self._leeway,
            )
        except jwt.PyJWTError as exc:
            logger.info("token rejected", extra={"reason": type(exc).__name__})
            raise AuthError("invalid token") from exc
        return Principal(
            user_id=str(claims["sub"]), email=claims.get("email"), roles=roles_from_claims(claims)
        )
