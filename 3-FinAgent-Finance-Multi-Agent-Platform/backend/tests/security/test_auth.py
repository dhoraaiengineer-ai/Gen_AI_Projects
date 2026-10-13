"""Supabase JWT verification: ES256 via JWKS, issuer/audience/expiry, clock-skew leeway, role and
tenant only from app_metadata."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from src.core.domain import Role
from src.core.errors import Forbidden, Unauthorized
from src.security.auth import JwtVerifier

ISSUER = "https://example.supabase.co/auth/v1"
TENANT = "0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01"
KEY = ec.generate_private_key(ec.SECP256R1())


def _verifier() -> JwtVerifier:
    verifier = JwtVerifier("https://example.supabase.co/auth/v1/.well-known/jwks.json", ISSUER)
    signing = SimpleNamespace(key=KEY.public_key())
    verifier._jwks = SimpleNamespace(get_signing_key_from_jwt=lambda token: signing)  # type: ignore[assignment]
    return verifier


def _token(alg: str = "ES256", key: Any = KEY, **overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 600,
        "email": "risk@northwind.example.com",
        "app_metadata": {"app_role": "risk_manager", "tenant_id": TENANT},
        "user_metadata": {"app_role": "admin"},  # user-editable: must be ignored
    } | overrides
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": "k1"})


async def test_valid_token_role_and_tenant_from_app_metadata() -> None:
    principal = await _verifier().verify(_token())
    assert principal.role == Role.RISK_MANAGER and principal.tenant_id == TENANT


async def test_small_clock_skew_is_tolerated() -> None:
    issued_ahead = int(time.time()) + 10  # issuer clock 10 s ahead of ours
    assert (await _verifier().verify(_token(iat=issued_ahead, nbf=issued_ahead))).user_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 120},
        {"iss": "https://evil.example.com/auth/v1"},
        {"aud": "anon"},
        {"iat": int(time.time()) + 3600, "nbf": int(time.time()) + 3600},
    ],
)
async def test_rejected_claims(overrides: dict[str, Any]) -> None:
    with pytest.raises(Unauthorized):
        await _verifier().verify(_token(**overrides))


async def test_symmetric_algorithm_rejected() -> None:
    with pytest.raises(Unauthorized):
        await _verifier().verify(_token(alg="HS256", key="x" * 32))


async def test_missing_tenant_is_forbidden() -> None:
    with pytest.raises(Forbidden):
        await _verifier().verify(_token(app_metadata={"app_role": "analyst"}))
