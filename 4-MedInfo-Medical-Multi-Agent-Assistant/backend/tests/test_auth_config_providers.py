"""Token verification, settings validation, provider error classification, logging format."""

from __future__ import annotations

import logging

import httpx
import jwt
import openai
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app.config import parse_chain
from app.core.auth import AuthError, TokenVerifier, roles_from_claims
from app.core.errors import ProviderError, ProviderQuotaError, ProviderUnavailableError
from app.core.logging import TextFormatter
from app.rag.providers import classify_provider_exception
from tests.conftest import ISSUER, make_settings
from tests.fakes import StaticKeyResolver


# ---- auth ---------------------------------------------------------------------------------------
@pytest.fixture
def verifier(ec_key) -> TokenVerifier:
    return TokenVerifier(StaticKeyResolver(ec_key.public_key()), "authenticated", ISSUER)


def test_valid_es256_token(verifier, token_factory) -> None:
    p = verifier.verify(token_factory("clinician"))
    assert p.user_id == "user-123" and p.top_role == "clinician"


def test_rs256_token_accepted() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    v = TokenVerifier(StaticKeyResolver(key.public_key()), "authenticated", None)
    token = jwt.encode({"sub": "u", "aud": "authenticated", "exp": 9999999999}, key, algorithm="RS256")
    assert v.verify(token).user_id == "u"


def test_hs256_rejected(verifier, token_factory) -> None:
    token = token_factory(key="shared-secret-not-allowed-0123456789abcdef", alg="HS256")
    with pytest.raises(AuthError, match="algorithm"):
        verifier.verify(token)


def test_alg_none_rejected(verifier) -> None:
    token = jwt.encode({"sub": "u", "aud": "authenticated", "exp": 9999999999}, None, algorithm="none")
    with pytest.raises(AuthError):
        verifier.verify(token)


def test_expired_and_wrong_audience_rejected(verifier, token_factory) -> None:
    with pytest.raises(AuthError):
        verifier.verify(token_factory(exp_in=-120))  # beyond the 30 s clock-skew leeway
    with pytest.raises(AuthError):
        verifier.verify(token_factory(aud="someone-else"))


def test_roles_only_from_app_metadata() -> None:
    assert roles_from_claims({"role": "admin"}) == frozenset({"user"})
    assert roles_from_claims({"app_metadata": {"roles": ["clinician", "bogus"]}}) == frozenset({"clinician"})
    assert roles_from_claims({"user_metadata": {"role": "admin"}}) == frozenset({"user"})


# ---- settings -----------------------------------------------------------------------------------
def test_chain_parsing() -> None:
    refs = parse_chain("euri:gpt-4.1-mini, groq:openai/gpt-oss-120b")
    assert [r.label for r in refs] == ["euri:gpt-4.1-mini", "groq:openai/gpt-oss-120b"]
    with pytest.raises(ValueError):
        parse_chain("openai:gpt-4")


@pytest.mark.parametrize("temp", [0.0, 0.5, 1.0])
def test_answer_temperature_bounds(temp: float) -> None:
    with pytest.raises(ValidationError):
        make_settings(llm_temperature=temp)


def test_production_requires_explicit_emergency_number() -> None:
    base = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://u:p@h/db",
        "conversation_encryption_key": "k" * 44,
    }
    with pytest.raises(ValidationError, match="EMERGENCY_NUMBER"):
        from app.config import Settings

        Settings(_env_file=None, supabase_url="https://x.supabase.co", **base)
    make_settings(**base, emergency_number="108")  # explicit -> fine


def test_jwks_url_derived_from_supabase_url() -> None:
    assert (
        make_settings().supabase_jwks_url == "https://example-test.supabase.co/auth/v1/.well-known/jwks.json"
    )


def test_secrets_are_masked() -> None:
    s = make_settings(euri_api_key="euri-should-not-print")
    assert "euri-should-not-print" not in repr(s)


# ---- provider error mapping ---------------------------------------------------------------------
def _resp(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status, headers=headers, request=httpx.Request("POST", "https://provider.test/v1/chat")
    )


def test_rate_limit_maps_to_quota_with_retry_after() -> None:
    exc = openai.RateLimitError("slow down", response=_resp(429, {"retry-after": "12"}), body=None)
    err = classify_provider_exception(exc, "m")
    assert isinstance(err, ProviderQuotaError) and err.retry_after == 12


def test_gateway_403_quota_maps_to_429() -> None:
    exc = openai.PermissionDeniedError("Daily quota exceeded for this key", response=_resp(403), body=None)
    assert isinstance(classify_provider_exception(exc, "m"), ProviderQuotaError)


def test_plain_403_maps_to_provider_error() -> None:
    exc = openai.PermissionDeniedError("model not enabled", response=_resp(403), body=None)
    assert isinstance(classify_provider_exception(exc, "m"), ProviderError)


def test_connection_error_maps_to_unavailable() -> None:
    exc = openai.APIConnectionError(request=httpx.Request("POST", "https://provider.test"))
    assert isinstance(classify_provider_exception(exc, "m"), ProviderUnavailableError)


def test_server_error_maps_to_provider_error() -> None:
    exc = openai.InternalServerError("boom", response=_resp(500), body=None)
    assert isinstance(classify_provider_exception(exc, "m"), ProviderError)


# ---- logging ------------------------------------------------------------------------------------
def test_text_log_format_prints_extra_fields() -> None:
    record = logging.LogRecord("x", logging.WARNING, __file__, 1, "provider call failed", (), None)
    record.error = "RateLimitError"
    record.request_id = "abc"
    out = TextFormatter().format(record)
    assert "error='RateLimitError'" in out and "[abc]" in out


def test_production_requires_conversation_encryption_key() -> None:
    with pytest.raises(ValidationError, match="CONVERSATION_ENCRYPTION_KEY"):
        make_settings(
            app_env="production", database_url="postgresql+psycopg://u:p@h/db", emergency_number="108"
        )


def test_small_clock_skew_is_tolerated_but_future_tokens_are_not(ec_key) -> None:
    """Regression: a Supabase token issued 'now' was rejected (ImmatureSignatureError) because the local
    clock was slightly behind. A small leeway accepts it; a token far in the future is still rejected."""
    import time

    verifier = TokenVerifier(
        StaticKeyResolver(ec_key.public_key()), "authenticated", ISSUER, leeway_seconds=30
    )

    def token(iat_offset: int) -> str:
        now = int(time.time())
        claims = {
            "sub": "u",
            "aud": "authenticated",
            "iss": ISSUER,
            "iat": now + iat_offset,
            "nbf": now + iat_offset,
            "exp": now + 3600,
            "app_metadata": {"role": "user"},
        }
        return jwt.encode(claims, ec_key, algorithm="ES256")

    assert verifier.verify(token(10)).user_id == "u"  # 10 s ahead: tolerated
    with pytest.raises(AuthError):
        verifier.verify(token(300))  # 5 min ahead: rejected
