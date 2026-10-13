"""Request-ID middleware, error envelope and readiness with a fake container."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api.main import create_app
from src.config.settings import Settings
from src.container import Container
from src.core.errors import QuotaExceeded


class Body(BaseModel):
    amount: float


def _fake_container(*, db_ok: bool = True) -> Container:
    container = Container(settings=Settings(_env_file=None))  # type: ignore[call-arg]

    async def ping() -> None:
        if not db_ok:
            raise ConnectionError("db down")

    container.health_checks["database"] = ping
    return container


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(container=_fake_container())
    router = APIRouter(prefix="/test")

    @router.get("/quota")
    async def quota() -> None:
        raise QuotaExceeded("euri quota exhausted", details={"provider": "euri"})

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @router.post("/body")
    async def body(payload: Body) -> dict[str, float]:
        return {"amount": payload.amount}

    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    response = client.get("/health")
    assert response.headers["x-request-id"].startswith("req_")


def test_safe_caller_request_id_is_kept_and_unsafe_one_replaced(client: TestClient) -> None:
    kept = client.get("/health", headers={"X-Request-ID": "abc-12345"})
    assert kept.headers["x-request-id"] == "abc-12345"
    replaced = client.get("/health", headers={"X-Request-ID": "bad id <script>"})
    assert replaced.headers["x-request-id"].startswith("req_")


def test_app_error_maps_to_status_with_request_id(client: TestClient) -> None:
    response = client.get("/test/quota", headers={"X-Request-ID": "quota-test-1"})
    assert response.status_code == 429
    assert response.json()["error"] == {
        "code": "quota_exceeded",
        "message": "euri quota exhausted",
        "requestId": "quota-test-1",
        "details": {"provider": "euri"},
    }


def test_unhandled_error_is_500_without_internals(client: TestClient) -> None:
    response = client.get("/test/boom")
    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["requestId"] == response.headers["x-request-id"]


def test_validation_error_envelope(client: TestClient) -> None:
    response = client.post("/test/body", json={"amount": "lots"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"][0]["loc"] == ["body", "amount"]


def test_not_found_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_readiness_ok_and_unavailable() -> None:
    with TestClient(create_app(container=_fake_container())) as c:
        assert c.get("/health/ready").json() == {"status": "ok", "checks": {"database": "ok"}}
    with TestClient(create_app(container=_fake_container(db_ok=False))) as c:
        response = c.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["database"] == "unavailable"
        assert "db down" not in response.text
