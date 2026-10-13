"""Call any API endpoint as a demo user (signs in with Supabase, prints status, limits and JSON).

    uv run python -m scripts.api_call compliance GET /api/v1/approvals
    uv run python -m scripts.api_call pm POST /api/v1/analyze/rebalance '{"portfolioId": "PF-A"}'
    uv run python -m scripts.api_call pm@contoso.example.com GET /api/v1/portfolios

USER is a full e-mail or the part before ``@northwind.example.com``. In Git Bash set
``MSYS_NO_PATHCONV=1`` so the path is not rewritten as a Windows path.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from scripts.ask import sign_in
from src.config.settings import get_settings


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("user")
    parser.add_argument("method", choices=["GET", "POST", "DELETE"])
    parser.add_argument("path")
    parser.add_argument("body", nargs="?", default=None, help="JSON body")
    parser.add_argument("--api", default=f"http://127.0.0.1:{get_settings().api_port}")
    parser.add_argument("--max-chars", type=int, default=8000)
    args = parser.parse_args()
    email = args.user if "@" in args.user else f"{args.user}@northwind.example.com"
    token = sign_in(email)
    response = httpx.request(
        args.method,
        f"{args.api}{args.path}",
        json=json.loads(args.body) if args.body else None,
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,
    )
    limits = {
        k: v
        for k, v in response.headers.items()
        if k.startswith("x-ratelimit") or k == "retry-after"
    }
    print(response.status_code, limits)
    try:
        print(
            json.dumps(response.json(), indent=1, default=str, ensure_ascii=False)[: args.max_chars]
        )
    except ValueError:
        print(response.text[: args.max_chars])
    return 0 if response.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
