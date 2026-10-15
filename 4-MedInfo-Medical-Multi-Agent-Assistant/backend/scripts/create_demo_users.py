"""Create (or reset) confirmed demo accounts in Supabase Auth, one per role, for local testing.

Uses the service-role SUPABASE_SECRET_KEY from .env (server-side only; never printed). Passwords are
random. Roles are set in app_metadata (the only place the app reads roles from).

Usage: python scripts/create_demo_users.py
"""

from __future__ import annotations

import secrets
import string
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

ACCOUNTS = [
    ("admin", "medinfo.admin@example.com"),
    ("clinician", "medinfo.clinician@example.com"),
    ("user", "medinfo.user@example.com"),
]


def password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(n))
    return core[:8] + "-" + core[8:] + "!"


def main() -> int:
    s = get_settings()
    if not s.supabase_url or s.supabase_secret_key is None:
        sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")
    key = s.supabase_secret_key.get_secret_value()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = f"{s.supabase_url}/auth/v1/admin/users"
    with httpx.Client(timeout=20, trust_env=False) as http:
        existing = {}
        res = http.get(base, headers=headers, params={"per_page": 200})
        if res.status_code >= 400:
            print(f"Could not list users: HTTP {res.status_code} {res.text[:200]}")
            return 1
        for u in res.json().get("users", []):
            existing[u.get("email")] = u["id"]
        print(f"{'role':10} {'email':34} password")
        for role, email in ACCOUNTS:
            pw = password()
            body = {"email": email, "password": pw, "email_confirm": True, "app_metadata": {"role": role}}
            if email in existing:
                r = http.put(f"{base}/{existing[email]}", headers=headers, json=body)
            else:
                r = http.post(base, headers=headers, json=body)
            if r.status_code >= 400:
                print(f"{role:10} {email:34} FAILED: HTTP {r.status_code} {r.text[:200]}")
                continue
            print(f"{role:10} {email:34} {pw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
