"""Cross-service integration tests against a RUNNING stack (frontend nginx -> backend -> Postgres/Redis).

Skipped unless MEDINFO_STACK_URL is set, e.g. after `docker compose up --build`:
    MEDINFO_STACK_URL=http://127.0.0.1:8080 python -m pytest tests/integration -q

They need no credentials and make no model calls (only unauthenticated endpoints and auth failures).
"""

from __future__ import annotations

import os

import httpx
import pytest

BASE = os.environ.get("MEDINFO_STACK_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="set MEDINFO_STACK_URL to run against a running stack")


@pytest.fixture(scope="module")
def http() -> httpx.Client:
    with httpx.Client(base_url=BASE, timeout=15, trust_env=False) as client:
        yield client


def test_ui_served_with_strict_headers(http: httpx.Client) -> None:
    res = http.get("/")
    assert res.status_code == 200
    assert "Information only, not medical advice" in res.text
    csp = res.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert res.headers["x-frame-options"] == "DENY"
    assert http.get("/static/app.js").headers["cache-control"] == "no-cache"


def test_api_is_proxied_to_the_backend(http: httpx.Client) -> None:
    cfg = http.get("/api/config").json()
    assert cfg["emergency_number"] and "supabase_url" in cfg
    assert "sb_secret" not in str(cfg)


def test_protected_routes_need_a_token(http: httpx.Client) -> None:
    assert http.post("/api/chat", json={"question": "What is hypertension?"}).status_code == 401
    assert http.get("/api/admin/documents").status_code == 401
    assert http.post("/api/chat", json={"question": "x"}, headers={"Authorization": "Bearer junk"}).status_code == 401


def test_backend_internals_not_exposed_through_frontend(http: httpx.Client) -> None:
    for path in ("/metrics", "/docs", "/openapi.json", "/readyz"):
        assert http.get(path).status_code == 404, path
