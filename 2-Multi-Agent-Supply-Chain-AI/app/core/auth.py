"""Supabase JWT verification.

- Tokens are verified against the project's JWKS with asymmetric algorithms only (ES256/RS256).
- The role comes only from `app_metadata.app_role` (set server-side); the top-level `role` claim is
  Supabase's Postgres role and is ignored.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from app.core.errors import Unauthorized
from app.core.metrics import AUTH_FAILURES
from app.core.rbac import Role, User

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = ["ES256", "RS256"]


class TokenVerifier(Protocol):
    def verify(self, token: str) -> User: ...


def user_from_claims(claims: dict[str, Any]) -> User:
    app_meta = claims.get("app_metadata") or {}
    user_meta = claims.get("user_metadata") or {}
    email = str(claims.get("email") or "")
    name = str(user_meta.get("full_name") or user_meta.get("name") or email.split("@", maxsplit=1)[0] or "User")
    return User(id=str(claims["sub"]), email=email, name=name, role=Role.parse(app_meta.get("app_role")))


class JwksVerifier:
    """Verifies Supabase access tokens. Keys are cached by PyJWKClient and refreshed on unknown `kid`."""

    def __init__(self, jwks_url: str, audience: str, issuer: str | None = None) -> None:
        if not jwks_url:
            raise ValueError("SUPABASE_JWKS_URL is required for authentication")
        self._client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600, timeout=5)
        self._audience = audience
        self._issuer = issuer

    def verify(self, token: str) -> User:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in ALLOWED_ALGORITHMS:
                AUTH_FAILURES.labels("algorithm").inc()
                raise Unauthorized("Unsupported token algorithm.")
            key = self._client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud"]},
            )
        except Unauthorized:
            raise
        except jwt.ExpiredSignatureError as exc:
            AUTH_FAILURES.labels("expired").inc()
            raise Unauthorized("Your session has expired. Sign in again.") from exc
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            AUTH_FAILURES.labels("invalid").inc()
            logger.info("token rejected", extra={"reason": type(exc).__name__})
            raise Unauthorized("Invalid credentials.") from exc
        return user_from_claims(claims)
