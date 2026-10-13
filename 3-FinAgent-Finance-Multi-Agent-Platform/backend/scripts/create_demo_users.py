"""Create (or update) demo users per role in Supabase Auth — idempotent.

Uses the Supabase Admin API with SUPABASE_SECRET_KEY; every user gets DEMO_USER_PASSWORD (from
.env, never printed) and ``app_metadata = {app_role, tenant_id}`` (not user-editable). Also upserts
a profile row in the tenant-scoped ``users`` table.

Usage: uv run python -m scripts.create_demo_users
"""

from __future__ import annotations

import sys

import httpx
import psycopg

from src.config.settings import get_settings
from src.core.tenancy import DEMO_TENANT_ID, SECOND_TENANT_ID

NORTHWIND, CONTOSO = str(DEMO_TENANT_ID), str(SECOND_TENANT_ID)
DEMO_USERS = [
    ("admin@northwind.example.com", "admin", NORTHWIND, "Northwind Admin"),
    ("pm@northwind.example.com", "portfolio_manager", NORTHWIND, "Northwind Portfolio Manager"),
    ("risk@northwind.example.com", "risk_manager", NORTHWIND, "Northwind Risk Manager"),
    ("compliance@northwind.example.com", "compliance_officer", NORTHWIND, "Northwind Compliance"),
    ("analyst@northwind.example.com", "analyst", NORTHWIND, "Northwind Analyst"),
    ("fraud@northwind.example.com", "fraud_analyst", NORTHWIND, "Northwind Fraud Analyst"),
    ("viewer@northwind.example.com", "viewer", NORTHWIND, "Northwind Viewer"),
    ("pm@contoso.example.com", "portfolio_manager", CONTOSO, "Contoso Portfolio Manager"),
]


def main() -> int:
    s = get_settings()
    if not (s.supabase_url and s.supabase_secret_key and s.demo_user_password):
        print("SUPABASE_URL, SUPABASE_SECRET_KEY and DEMO_USER_PASSWORD must be set in .env")
        return 2
    secret = s.supabase_secret_key.get_secret_value()
    headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}
    base = f"{s.supabase_url.rstrip('/')}/auth/v1/admin/users"
    password = s.demo_user_password.get_secret_value()
    with httpx.Client(timeout=20, headers=headers) as http:
        listing = http.get(base, params={"per_page": 1000})
        listing.raise_for_status()
        existing = {u["email"]: u["id"] for u in listing.json().get("users", [])}
        created: list[tuple[str, str, str, str]] = []
        for email, role, tenant, name in DEMO_USERS:
            body = {
                "password": password,
                "email_confirm": True,
                "app_metadata": {"app_role": role, "tenant_id": tenant},
                "user_metadata": {"display_name": name},
            }
            if email in existing:
                response = http.put(f"{base}/{existing[email]}", json=body)
                action = "updated"
            else:
                response = http.post(base, json={"email": email, **body})
                action = "created"
            if response.status_code >= 400:
                print(f"FAILED {email}: HTTP {response.status_code} {response.text[:200]}")
                return 1
            user_id = response.json()["id"]
            created.append((user_id, email, role, tenant))
            print(
                f"{action:8} {email:36} role={role:18} tenant={'northwind' if tenant == NORTHWIND else 'contoso'}"
            )
    url = s.session_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, prepare_threshold=None) as conn, conn.transaction():
        for user_id, email, role, tenant in created:
            conn.execute(
                "INSERT INTO users (id, tenant_id, email, display_name, role, is_active) "
                "VALUES (%s, %s, %s, %s, %s, true) ON CONFLICT (id) DO UPDATE SET role = EXCLUDED.role, "
                "tenant_id = EXCLUDED.tenant_id, email = EXCLUDED.email, updated_at = now()",
                (user_id, tenant, email, email.split("@")[0], role),
            )
    print(f"{len(created)} demo users ready; password = DEMO_USER_PASSWORD in .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
