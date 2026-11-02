from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import InvalidTransition
from app.main import create_app


def _app_with_test_routes() -> FastAPI:
    app = create_app()

    @app.get("/_test/domain-error")
    async def _domain() -> None:
        raise InvalidTransition(details={"from": "BOOKED", "to": "CLOSED"})

    @app.get("/_test/crash")
    async def _crash() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/_test/validate")
    async def _validate(n: int) -> dict[str, int]:
        return {"n": n}

    return app


client = TestClient(_app_with_test_routes(), raise_server_exceptions=False)


def test_unknown_route_returns_not_found_envelope() -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_domain_error_maps_to_code_and_status() -> None:
    resp = client.get("/_test/domain-error")
    assert resp.status_code == 409
    err = resp.json()["error"]
    assert err["code"] == "INVALID_TRANSITION"
    assert err["details"] == {"from": "BOOKED", "to": "CLOSED"}


def test_validation_error_is_400_with_fields() -> None:
    resp = client.get("/_test/validate", params={"n": "abc"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["details"]["fields"]


def test_unhandled_error_does_not_leak_internals() -> None:
    resp = client.get("/_test/crash")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in resp.text
    assert body["request_id"]
