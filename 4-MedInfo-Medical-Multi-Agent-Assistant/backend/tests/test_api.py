"""Health probes, auth on routes, error mapping, security headers."""

from __future__ import annotations

import pytest

from app.core.errors import ProviderError, ProviderQuotaError, ProviderUnavailableError
from tests.fakes import FakeChatModel, FakeProbe, cited


def test_liveness_never_checks_dependencies(client_factory) -> None:
    client, _ = client_factory(probe=FakeProbe(ok=False))
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readiness_checks_database(client_factory) -> None:
    client, _ = client_factory(probe=FakeProbe(ok=True))
    assert client.get("/readyz").status_code == 200
    client, _ = client_factory(probe=FakeProbe(ok=False))
    res = client.get("/readyz")
    assert res.status_code == 503 and res.json()["database"] == "unreachable"


def test_chat_requires_sign_in(client_factory) -> None:
    client, _ = client_factory()
    assert client.post("/api/chat", json={"question": "What is hypertension?"}).status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.post("/api/chat", json={"question": "x"}, headers=bad).status_code == 401


def test_admin_route_requires_admin(client_factory, token_factory) -> None:
    client, _ = client_factory()
    user = {"Authorization": f"Bearer {token_factory('user')}"}
    clin = {"Authorization": f"Bearer {token_factory('clinician')}"}
    admin = {"Authorization": f"Bearer {token_factory('admin')}"}
    assert client.get("/api/admin/safety-rules", headers=user).status_code == 403
    assert client.get("/api/admin/safety-rules", headers=clin).status_code == 403
    assert client.get("/api/admin/safety-rules", headers=admin).status_code == 200


def test_top_level_role_claim_is_ignored(client_factory, token_factory) -> None:
    client, _ = client_factory()
    token = token_factory(role=None, top_level_role="admin")
    res = client.get("/api/admin/safety-rules", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_me_reports_role(client_factory, token_factory) -> None:
    client, _ = client_factory()
    res = client.get("/api/me", headers={"Authorization": f"Bearer {token_factory('clinician')}"})
    assert res.json()["role"] == "clinician"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProviderQuotaError(retry_after=30), 429),
        (ProviderError(), 502),
        (ProviderUnavailableError(), 503),
    ],
)
def test_provider_errors_map_to_status(client_factory, auth_header, error, status) -> None:
    client, _ = client_factory(FakeChatModel(answer=error))
    res = client.post("/api/chat", json={"question": "What is hypertension?"}, headers=auth_header)
    assert res.status_code == status
    if status == 429:
        assert res.headers["Retry-After"] == "30"


def test_question_length_limit(client_factory, auth_header) -> None:
    client, _ = client_factory(max_question_chars=100)
    res = client.post("/api/chat", json={"question": "a" * 101}, headers=auth_header)
    assert res.status_code == 422


def test_security_headers_and_ui(client_factory) -> None:
    client, _ = client_factory()
    res = client.get("/")
    assert res.status_code == 200
    assert "Information only, not medical advice" in res.text
    csp = res.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "https://example-test.supabase.co" in csp


def test_public_config_has_no_secrets(client_factory) -> None:
    client, _ = client_factory(supabase_secret_key="sb_secret_should_not_leak")
    body = client.get("/api/config").text
    assert "sb_secret" not in body
    assert "112" in body


def test_api_responses_not_cached(client_factory, auth_header) -> None:
    client, _ = client_factory(
        FakeChatModel(answer=cited("Hypertension often causes no symptoms {a}.", a="no symptoms"))
    )
    res = client.post("/api/chat", json={"question": "What is hypertension?"}, headers=auth_header)
    assert res.headers["Cache-Control"] == "no-store"
