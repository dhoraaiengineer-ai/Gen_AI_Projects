"""JWT verification for Supabase Auth access tokens.

Supabase signs access tokens with an asymmetric key (ES256 for this project) and publishes the
public half at /auth/v1/.well-known/jwks.json, so the API verifies tokens without any secret.

Roles: every signed-in user is `user`. A user becomes `admin` when an admin sets
`app_metadata.app_role = "admin"` in Supabase. app_metadata is writable only server-side, so
users can't grant themselves a role. (The top-level `role` claim is always "authenticated" and
is Supabase's Postgres role, not ours.)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import jwt

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = ["ES256", "RS256"]  # asymmetric only; never accept HS256/none


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN


class AuthError(Exception):
    """Token missing, malformed, expired, or signed by the wrong issuer."""


KeyResolver = Callable[[str], Any]  # token -> public key used to verify it


class TokenVerifier:
    def __init__(self, key_resolver: KeyResolver, issuer: str, audience: str, leeway_seconds: int = 30):
        self._key_resolver = key_resolver
        self.issuer = issuer
        self.audience = audience
        self.leeway_seconds = leeway_seconds

    def verify(self, token: str) -> Principal:
        try:
            key = self._key_resolver(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_seconds,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError(str(exc)) from exc

        app_role = (claims.get("app_metadata") or {}).get("app_role")
        role = Role.ADMIN if app_role == Role.ADMIN else Role.USER
        return Principal(user_id=str(claims["sub"]), email=claims.get("email"), role=role)


def build_supabase_verifier(jwks_url: str, issuer: str, audience: str) -> TokenVerifier:
    # PyJWKClient caches keys and refetches on an unknown `kid`, so key rotation in Supabase just works.
    client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600, timeout=10)

    def resolve(token: str) -> Any:
        return client.get_signing_key_from_jwt(token).key

    return TokenVerifier(resolve, issuer=issuer, audience=audience)
