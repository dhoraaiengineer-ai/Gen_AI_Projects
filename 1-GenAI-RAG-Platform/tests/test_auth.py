import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import Settings
from app.container import build_verifier
from app.core.auth import AuthError, Role
from tests.conftest import AppHarness, make_test_verifier, make_token

QUERY = {"question": "Anything?"}
INGEST = {"documents": [{"text": "Paris is the capital of France.", "source": "geo.md"}]}


# ---------- TokenVerifier ----------


def test_valid_token_yields_principal() -> None:
    p = make_test_verifier().verify(make_token(sub="u1", email="a@b.c"))
    assert (p.user_id, p.email, p.role) == ("u1", "a@b.c", Role.USER)


def test_admin_role_comes_from_app_metadata_only() -> None:
    assert make_test_verifier().verify(make_token("admin")).role is Role.ADMIN
    # Unknown app roles fall back to plain user.
    assert make_test_verifier().verify(make_token("superuser")).role is Role.USER


@pytest.mark.parametrize(
    "token",
    [
        make_token(expires_in=-120),  # expired beyond the 30s leeway
        make_token(audience="anon"),
        make_token(issuer="https://evil.example.com/auth/v1"),
        make_token(key=ec.generate_private_key(ec.SECP256R1())),  # signed by someone else
        "not-a-jwt",
    ],
    ids=["expired", "wrong-audience", "wrong-issuer", "wrong-key", "garbage"],
)
def test_bad_tokens_rejected(token: str) -> None:
    with pytest.raises(AuthError):
        make_test_verifier().verify(token)


def test_symmetric_algorithm_rejected() -> None:
    forged = jwt.encode({"sub": "x", "aud": "authenticated"}, "s" * 32, algorithm="HS256")
    with pytest.raises(AuthError):
        make_test_verifier().verify(forged)


# ---------- API authentication / authorization ----------


def test_protected_endpoints_require_token(harness: AppHarness) -> None:
    with harness.client(role=None) as c:
        assert c.post("/api/v1/query", json=QUERY).status_code == 401
        assert c.post("/api/v1/agent", json={"task": "x"}).status_code == 401
        assert c.post("/api/v1/ingest", json=INGEST).status_code == 401
        r = c.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401(harness: AppHarness) -> None:
    expired = {"Authorization": f"Bearer {make_token(expires_in=-120)}"}
    with harness.client(role=None) as c:
        assert c.post("/api/v1/query", json=QUERY, headers=expired).status_code == 401


def test_public_endpoints_need_no_token(harness: AppHarness) -> None:
    with harness.client(role=None) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 200
        assert c.get("/").status_code == 200
        cfg = c.get("/api/v1/auth/config").json()
    assert cfg == {
        "enabled": True,
        "supabase_url": "https://test-project.supabase.co",
        "supabase_publishable_key": "sb_publishable_test",
    }


def test_user_can_query_but_not_ingest(harness: AppHarness) -> None:
    with harness.client(role="user") as c:
        assert c.post("/api/v1/query", json=QUERY).status_code == 200
        r = c.post("/api/v1/ingest", json=INGEST)
    assert r.status_code == 403
    assert r.json()["detail"] == "Admin role required"


def test_admin_can_ingest(harness: AppHarness) -> None:
    with harness.client(role="admin") as c:
        assert c.post("/api/v1/ingest", json=INGEST).status_code == 200


def test_me_returns_identity(harness: AppHarness) -> None:
    with harness.client(role="admin") as c:
        assert c.get("/api/v1/me").json() == {"user_id": "user-123", "email": "dev@example.com", "role": "admin"}


def test_auth_disabled_treats_caller_as_local_admin(harness: AppHarness) -> None:
    harness.auth_enabled = False
    with harness.client(role=None) as c:
        assert c.post("/api/v1/ingest", json=INGEST).status_code == 200
        assert c.get("/api/v1/me").json()["role"] == "admin"


def test_ui_csp_allows_supabase_auth(harness: AppHarness) -> None:
    with harness.client(role=None) as c:
        csp = c.get("/").headers["content-security-policy"]
    assert "connect-src 'self' https://test-project.supabase.co;" in csp


# ---------- Startup safety ----------


def test_auth_cannot_be_disabled_in_prod() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        build_verifier(Settings(_env_file=None, auth_enabled=False, environment="prod"))


def test_auth_enabled_without_supabase_url_fails_fast() -> None:
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        build_verifier(Settings(_env_file=None, auth_enabled=True))
