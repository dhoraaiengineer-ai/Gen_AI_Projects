from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import health
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_ok_envelope(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["data"] == {"status": "ok"}
    assert body["error"] is None
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_valid_incoming_request_id_is_echoed(client: TestClient) -> None:
    resp = client.get("/health", headers={"X-Request-ID": "req-12345678"})
    assert resp.headers["X-Request-ID"] == "req-12345678"
    assert resp.json()["request_id"] == "req-12345678"


def test_malformed_request_id_is_replaced(client: TestClient) -> None:
    resp = client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert resp.headers["X-Request-ID"] != "bad id with spaces"


async def _ok(_: Settings) -> health.CheckResult:
    return "ok"


async def _boom(_: Settings) -> health.CheckResult:
    raise ConnectionError("db down")


def test_ready_all_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "READY_CHECKS", {"db": _ok, "storage": _ok, "llm_config": _ok})
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"db": "ok", "storage": "ok", "llm_config": "ok"}


def test_ready_reports_failing_dependency_as_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "READY_CHECKS", {"db": _boom, "storage": _ok, "llm_config": _ok})
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_READY"
    assert body["error"]["details"] == {"db": "fail", "storage": "ok", "llm_config": "ok"}


async def test_llm_config_check_fails_without_keys() -> None:
    assert await health.check_llm_config(Settings(llm_agent_chain="euri:m", llm_answer_chain="groq:m")) == "fail"


async def test_llm_config_check_ok_with_keys() -> None:
    s = Settings(llm_agent_chain="euri:m", llm_answer_chain="groq:m", euri_api_key="k1", groq_api_key="k2")
    assert await health.check_llm_config(s) == "ok"
