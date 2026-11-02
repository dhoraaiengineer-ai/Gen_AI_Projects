"""P1-3 security tests: ownership (IDOR), dealer isolation, role enforcement, token tampering, login abuse."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest

from tests.conftest import DEMO_PASSWORD, TEST_JWT_SECRET, LoginFn

pytestmark = pytest.mark.integration

PRIYA = "owner.priya@example.test"
ARJUN = "owner.arjun@example.test"
ADVISOR_D1 = "advisor.d1@autoserve.example.test"
ADVISOR_D2 = "advisor.d2@autoserve.example.test"
TECH_D1 = "tech.d1@autoserve.example.test"
WARRANTY_D1 = "warranty.d1@autoserve.example.test"
WARRANTY_D2 = "warranty.d2@autoserve.example.test"
ADMIN = "admin@autoserve.example.test"


async def _ids(api: httpx.AsyncClient, headers: dict[str, str], path: str) -> list[str]:
    resp = await api.get(path, headers=headers)
    assert resp.status_code == 200, resp.text
    return [item["id"] for item in resp.json()["data"]["items"]]


# ── Ownership (owner A cannot read owner B's data) ─────────────────────────────────────────────────────
async def test_owner_sees_only_own_vehicles(api: httpx.AsyncClient, login: LoginFn) -> None:
    priya = await _ids(api, await login(PRIYA), "/api/v1/vehicles")
    arjun = await _ids(api, await login(ARJUN), "/api/v1/vehicles")
    assert len(priya) == 2 and len(arjun) == 4
    assert not set(priya) & set(arjun)


async def test_owner_cannot_read_other_owners_vehicle(api: httpx.AsyncClient, login: LoginFn) -> None:
    arjun_vehicle = (await _ids(api, await login(ARJUN), "/api/v1/vehicles"))[0]
    resp = await api.get(f"/api/v1/vehicles/{arjun_vehicle}", headers=await login(PRIYA))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_owner_reads_own_vehicle_with_full_vin_and_decode(api: httpx.AsyncClient, login: LoginFn) -> None:
    headers = await login(PRIYA)
    vid = (await _ids(api, headers, "/api/v1/vehicles"))[0]
    data = (await api.get(f"/api/v1/vehicles/{vid}", headers=headers)).json()["data"]
    assert len(data["vin"]) == 17 and data["vin"].startswith("VLX")
    assert data["decoded"]["model"] == data["model"]


async def test_vehicle_list_masks_vin(api: httpx.AsyncClient, login: LoginFn) -> None:
    resp = await api.get("/api/v1/vehicles", headers=await login(PRIYA))
    for item in resp.json()["data"]["items"]:
        assert item["vin_masked"].startswith("***") and len(item["vin_masked"]) == 9


async def test_owner_cannot_read_other_owners_repair_order(api: httpx.AsyncClient, login: LoginFn) -> None:
    arjun_ros = await _ids(api, await login(ARJUN), "/api/v1/repair-orders")
    priya_ros = await _ids(api, await login(PRIYA), "/api/v1/repair-orders")
    assert arjun_ros and priya_ros and not set(arjun_ros) & set(priya_ros)
    resp = await api.get(f"/api/v1/repair-orders/{arjun_ros[0]}", headers=await login(PRIYA))
    assert resp.status_code == 404


# ── Dealer isolation ──────────────────────────────────────────────────────────────────────────────────
async def test_staff_see_only_their_dealers_repair_orders(api: httpx.AsyncClient, login: LoginFn) -> None:
    """Isolation, not seed counts: other integration tests may book extra ROs before this runs."""
    for email, minimum in ((ADVISOR_D1, 6), (ADVISOR_D2, 4)):
        h = await login(email)
        own_dealer = (await api.get("/api/v1/auth/me", headers=h)).json()["data"]["dealer_name"]
        ids = await _ids(api, h, "/api/v1/repair-orders?limit=100")
        assert len(ids) >= minimum
        for ro_id in ids:
            detail = (await api.get(f"/api/v1/repair-orders/{ro_id}", headers=h)).json()["data"]
            assert detail["dealer"]["name"] == own_dealer
    d1 = await _ids(api, await login(ADVISOR_D1), "/api/v1/repair-orders?limit=100")
    d2 = await _ids(api, await login(ADVISOR_D2), "/api/v1/repair-orders?limit=100")
    assert not set(d1) & set(d2)


@pytest.mark.parametrize("reader", [ADVISOR_D1, TECH_D1, WARRANTY_D1])
async def test_dealer1_staff_cannot_read_dealer2_repair_order(
    api: httpx.AsyncClient, login: LoginFn, reader: str
) -> None:
    d2_ro = (await _ids(api, await login(ADVISOR_D2), "/api/v1/repair-orders"))[0]
    resp = await api.get(f"/api/v1/repair-orders/{d2_ro}", headers=await login(reader))
    assert resp.status_code == 404


async def test_dealer2_staff_cannot_read_dealer1_vehicle_context(api: httpx.AsyncClient, login: LoginFn) -> None:
    d1_vehicles = set(await _ids(api, await login(ADVISOR_D1), "/api/v1/vehicles"))
    d2_vehicles = set(await _ids(api, await login(WARRANTY_D2), "/api/v1/vehicles"))
    only_d1 = sorted(d1_vehicles - d2_vehicles)
    assert only_d1
    resp = await api.get(f"/api/v1/vehicles/{only_d1[0]}", headers=await login(WARRANTY_D2))
    assert resp.status_code == 404


async def test_repair_order_detail_has_real_timeline(api: httpx.AsyncClient, login: LoginFn) -> None:
    headers = await login(ADVISOR_D1)
    closed = (await api.get("/api/v1/repair-orders?status=CLOSED", headers=headers)).json()["data"]["items"]
    assert len(closed) == 1
    detail = (await api.get(f"/api/v1/repair-orders/{closed[0]['id']}", headers=headers)).json()["data"]
    assert [e["to_status"] for e in detail["timeline"]][-1] == "CLOSED"
    assert detail["timeline"][0]["to_status"] == "BOOKED"


# ── Role enforcement on every staff/admin endpoint ────────────────────────────────────────────────────
ROLE_MATRIX = [
    # (method, path, {email: expected_status})
    ("GET", "/api/v1/vehicles", {PRIYA: 200, ADVISOR_D1: 200, TECH_D1: 200, WARRANTY_D1: 200, ADMIN: 403}),
    ("GET", "/api/v1/repair-orders", {PRIYA: 200, ADVISOR_D1: 200, TECH_D1: 200, WARRANTY_D1: 200, ADMIN: 403}),
    ("GET", "/api/v1/admin/users", {PRIYA: 403, ADVISOR_D1: 403, TECH_D1: 403, WARRANTY_D1: 403, ADMIN: 200}),
    ("GET", "/api/v1/admin/audit/verify", {PRIYA: 403, ADVISOR_D1: 403, TECH_D1: 403, WARRANTY_D1: 403, ADMIN: 200}),
    ("GET", "/api/v1/auth/me", {PRIYA: 200, ADVISOR_D1: 200, TECH_D1: 200, WARRANTY_D1: 200, ADMIN: 200}),
]


@pytest.mark.parametrize(("method", "path", "expected"), ROLE_MATRIX)
async def test_role_matrix(
    api: httpx.AsyncClient, login: LoginFn, method: str, path: str, expected: dict[str, int]
) -> None:
    for email, status in expected.items():
        resp = await api.request(method, path, headers=await login(email))
        assert resp.status_code == status, f"{email} {method} {path} → {resp.status_code}"
        if status == 403:
            assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


@pytest.mark.parametrize("path", [p for _, p, _ in ROLE_MATRIX])
async def test_unauthenticated_requests_rejected(api: httpx.AsyncClient, path: str) -> None:
    resp = await api.get(path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_admin_create_user_requires_admin_and_dealer_rules(api: httpx.AsyncClient, login: LoginFn) -> None:
    body = {"email": "new.staff@autoserve.example.test", "display_name": "New Staff (SYNTHETIC)", "role": "technician"}
    assert (await api.post("/api/v1/admin/users", json=body, headers=await login(ADVISOR_D1))).status_code == 403
    resp = await api.post("/api/v1/admin/users", json=body, headers=await login(ADMIN))
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "VALIDATION_ERROR"  # staff without dealer


# ── Token tampering ───────────────────────────────────────────────────────────────────────────────────
def _claims(**over: object) -> dict[str, object]:
    now = datetime.now(UTC)
    base: dict[str, object] = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "role": "admin",
        "iss": "autoserve-demo",
        "aud": "autoserve-api",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    base.update(over)
    return base


async def _real_sub(api: httpx.AsyncClient, login: LoginFn, email: str) -> str:
    me = await api.get("/api/v1/auth/me", headers=await login(email))
    return str(me.json()["data"]["id"])


async def test_token_signed_with_wrong_secret_rejected(api: httpx.AsyncClient, login: LoginFn) -> None:
    sub = await _real_sub(api, login, ADMIN)
    token = jwt.encode(_claims(sub=sub), "attacker-secret-" + "y" * 40, algorithm="HS256")
    assert (await api.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_alg_none_token_rejected(api: httpx.AsyncClient, login: LoginFn) -> None:
    sub = await _real_sub(api, login, ADMIN)
    token = jwt.encode(_claims(sub=sub), key="", algorithm="none")
    assert (await api.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})).status_code == 401


@pytest.mark.parametrize(
    "override",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"aud": "someone-else"},
        {"iss": "evil-issuer"},
    ],
)
async def test_expired_or_wrong_audience_issuer_rejected(
    api: httpx.AsyncClient, login: LoginFn, override: dict[str, object]
) -> None:
    sub = await _real_sub(api, login, ADMIN)
    token = jwt.encode(_claims(sub=sub, **override), TEST_JWT_SECRET, algorithm="HS256")
    assert (await api.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_role_claim_in_token_is_not_trusted(api: httpx.AsyncClient, login: LoginFn) -> None:
    """A validly signed token for an owner that claims role=admin still gets owner permissions (role comes from DB)."""
    sub = await _real_sub(api, login, PRIYA)
    token = jwt.encode(_claims(sub=sub, role="admin"), TEST_JWT_SECRET, algorithm="HS256")
    assert (await api.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})).status_code == 403


# ── Login abuse ───────────────────────────────────────────────────────────────────────────────────────
async def test_login_errors_are_uniform(api: httpx.AsyncClient) -> None:
    wrong_pw = await api.post("/api/v1/auth/login", json={"email": PRIYA, "password": "nope"})
    no_user = await api.post("/api/v1/auth/login", json={"email": "ghost@example.test", "password": "nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


async def test_login_rate_limited(api: httpx.AsyncClient) -> None:
    statuses = [
        (await api.post("/api/v1/auth/login", json={"email": PRIYA, "password": "wrong"})).status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


async def test_login_success_returns_token_and_me(api: httpx.AsyncClient) -> None:
    resp = await api.post("/api/v1/auth/login", json={"email": ADVISOR_D1, "password": DEMO_PASSWORD})
    data = resp.json()["data"]
    assert resp.status_code == 200 and data["token_type"] == "bearer"
    assert data["user"]["role"] == "service_advisor" and data["user"]["dealer_name"].endswith("(SYNTHETIC)")


async def test_admin_creates_staff_user_once(api: httpx.AsyncClient, login: LoginFn) -> None:
    dealer_id = (await api.get("/api/v1/auth/me", headers=await login(ADVISOR_D1))).json()["data"]["dealer_id"]
    admin = await login(ADMIN)
    body = {
        "email": "tech.extra@autoserve.example.test",
        "display_name": "Extra Technician (SYNTHETIC)",
        "role": "technician",
        "dealer_id": dealer_id,
        "password": "Long-enough-demo-pw",
    }
    created = await api.post("/api/v1/admin/users", json=body, headers=admin)
    assert created.status_code == 201, created.text
    assert created.json()["data"]["role"] == "technician"
    dup = await api.post("/api/v1/admin/users", json=body, headers=admin)
    assert dup.status_code == 400
    listed = await api.get("/api/v1/admin/users", headers=admin)
    assert "tech.extra@autoserve.example.test" in [u["email"] for u in listed.json()["data"]["items"]]
    new_login = await api.post("/api/v1/auth/login", json={"email": body["email"], "password": body["password"]})
    assert new_login.status_code == 200
