"""Liveness probe: public, fast, data-free."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app


def test_liveness_is_public_and_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_is_404() -> None:
    client = TestClient(create_app())
    assert client.get("/api/v1/nope").status_code == 404
