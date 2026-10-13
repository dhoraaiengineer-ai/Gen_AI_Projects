"""Stage 8 API behaviour with a fake container: rate limits and headers, permission checks before
any work, public config without secrets, structured-analysis validation."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api.main import create_app
from src.config.settings import Settings
from src.container import Container
from src.core.domain import Role
from src.security.auth import Principal, require_user

TENANT = "0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01"


def _client(role: Role, **settings: object) -> TestClient:
    s = Settings(  # type: ignore[call-arg]
        _env_file=None,
        redis_enabled=False,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key=SecretStr("sb_publishable_test"),
        **settings,
    )
    app = create_app(container=Container(settings=s))
    principal = Principal(user_id="u-1", email="u@example.com", role=role, tenant_id=TENANT)
    app.dependency_overrides[require_user] = lambda: principal
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def viewer() -> Iterator[TestClient]:
    with _client(Role.VIEWER, rate_limit_read=2) as c:
        yield c


def test_rate_limit_headers_then_429_with_retry_after(viewer: TestClient) -> None:
    first = viewer.get("/api/v1/dashboard/ml/models")
    assert first.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "2"
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert {m["kind"] for m in first.json()} == {"fraud", "risk", "prediction"}
    viewer.get("/api/v1/dashboard/ml/models")
    blocked = viewer.get("/api/v1/dashboard/ml/models")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1
    assert blocked.headers["x-ratelimit-remaining"] == "0"


def test_permissions_checked_before_any_work(viewer: TestClient) -> None:
    for path, body in (
        ("/api/v1/analyze/risk", {"portfolioId": "PF-A"}),
        ("/api/v1/analyze/fraud", {"transactionId": "TX-1"}),
        ("/api/v1/chat", {"question": "hi"}),
        ("/api/v1/approvals/00000000-0000-0000-0000-000000000000/decision", {"approve": True}),
    ):
        assert viewer.post(path, json=body).status_code == 403, path
    assert viewer.get("/api/v1/audit/req_123456").status_code == 403
    assert viewer.get("/api/v1/dashboard/fraud").status_code == 403


def test_public_config_has_no_secrets() -> None:
    with _client(Role.VIEWER) as c:
        app = c.app
        app.dependency_overrides.clear()  # type: ignore[attr-defined]
        body = c.get("/api/v1/config/public").json()
    assert body["supabasePublishableKey"] == "sb_publishable_test"
    assert body["disclaimer"] == "Decision support only — not investment advice."
    assert not {"databaseUrl", "llmKeys", "serviceRoleKey"} & set(body)


def test_structured_analysis_validates_input() -> None:
    with _client(Role.RISK_MANAGER) as c:
        missing = c.post("/api/v1/analyze/risk", json={})
        bad = c.post("/api/v1/analyze/risk", json={"portfolioId": "DROP TABLE"})
    assert missing.status_code == 422 and "portfolioId" in missing.json()["error"]["message"]
    assert bad.status_code == 422


def test_approvers_without_propose_permission_can_list_approvals() -> None:
    # compliance_officer has approvals:decide but not portfolio:propose; the list must not 403.
    with _client(Role.COMPLIANCE_OFFICER) as c:
        response = c.get("/api/v1/approvals")
    assert response.status_code != 403
    with _client(Role.ANALYST) as c:
        assert c.get("/api/v1/approvals").status_code == 403
