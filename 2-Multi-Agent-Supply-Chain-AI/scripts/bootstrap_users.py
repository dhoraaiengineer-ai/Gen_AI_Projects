"""Create or update demo users in Supabase Auth, one per role, using the server-side secret key.

    uv run python scripts/bootstrap_users.py                 # create demo users (password saved to .env)
    uv run python scripts/bootstrap_users.py --promote EMAIL admin   # set the role of an existing account

Roles live in app_metadata.app_role, which only the service key can write — users can't change their own role.
"""

from __future__ import annotations

import argparse
import secrets
import string
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
DEMO_USERS = [
    ("admin@supplyai.example", "Demo Admin", "admin"),
    ("approver@supplyai.example", "Demo Approver", "approver"),
    ("analyst@supplyai.example", "Demo Analyst", "analyst"),
    ("viewer@supplyai.example", "Demo Viewer", "viewer"),
]
ROLES = {"viewer", "analyst", "approver", "admin"}


def _headers(secret: str) -> dict[str, str]:
    return {"apikey": secret, "Authorization": f"Bearer {secret}", "Content-Type": "application/json"}


def _find(client: httpx.Client, base: str, secret: str, email: str) -> dict | None:
    page = 1
    while True:
        r = client.get(f"{base}/auth/v1/admin/users", params={"page": page, "per_page": 200}, headers=_headers(secret))
        r.raise_for_status()
        users = r.json().get("users", [])
        for u in users:
            if (u.get("email") or "").lower() == email.lower():
                return u
        if len(users) < 200:
            return None
        page += 1


def _password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14)) + "!9a"


def _save_password(password: str) -> None:
    env = ROOT / ".env"
    text = env.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.startswith("DEMO_USER_PASSWORD=")]
    lines.append(f"DEMO_USER_PASSWORD={password}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--promote", nargs=2, metavar=("EMAIL", "ROLE"))
    args = parser.parse_args()
    s = get_settings()
    secret = s.supabase_secret_key.get_secret_value()
    if not (s.supabase_url and secret):
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")
    with httpx.Client(timeout=20) as client:
        if args.promote:
            email, role = args.promote
            if role not in ROLES:
                raise SystemExit(f"role must be one of {sorted(ROLES)}")
            user = _find(client, s.supabase_url, secret, email)
            if user is None:
                raise SystemExit(f"{email} has no account yet — sign up in the app first")
            r = client.put(f"{s.supabase_url}/auth/v1/admin/users/{user['id']}", headers=_headers(secret), json={"app_metadata": {"app_role": role}})
            r.raise_for_status()
            print(f"{email} is now {role} (sign out and back in to refresh the token)")
            return

        password = _password()
        for email, name, role in DEMO_USERS:
            body = {"email": email, "password": password, "email_confirm": True,
                    "user_metadata": {"full_name": name}, "app_metadata": {"app_role": role}}
            existing = _find(client, s.supabase_url, secret, email)
            if existing:
                r = client.put(f"{s.supabase_url}/auth/v1/admin/users/{existing['id']}", headers=_headers(secret), json=body)
            else:
                r = client.post(f"{s.supabase_url}/auth/v1/admin/users", headers=_headers(secret), json=body)
            r.raise_for_status()
            print(f"{'updated' if existing else 'created'} {email} ({role})")
        _save_password(password)
        print("Password saved to .env as DEMO_USER_PASSWORD (same for all demo users).")


if __name__ == "__main__":
    main()
