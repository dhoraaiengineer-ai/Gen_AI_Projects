"""Verify the browser (publishable) key can read nothing through Supabase's REST API.

Makes one HTTP GET per table. Exit code 1 if any table returns rows.
Usage: uv run python -m scripts.verify_rls
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

import src.db.models  # noqa: F401  (registers tables)
from src.config.settings import get_settings
from src.db.base import Base


def main() -> int:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_publishable_key):
        print("SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY not set")
        return 2
    key = settings.supabase_publishable_key.get_secret_value()
    leaks = 0
    extra = [
        "alembic_version",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
    ]
    for table in [*sorted(Base.metadata.tables), *extra]:
        request = urllib.request.Request(  # noqa: S310 - fixed https URL from settings
            f"{settings.supabase_url}/rest/v1/{table}?select=*&limit=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
                rows = json.loads(response.read().decode("utf-8"))
                status = f"HTTP {response.status}, {len(rows)} rows"
                leaks += bool(rows)
        except urllib.error.HTTPError as exc:
            status = f"HTTP {exc.code} (denied)"
        print(f"{table:22} {status}")
    print("RLS OK: publishable key reads nothing" if not leaks else f"LEAK in {leaks} tables")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
