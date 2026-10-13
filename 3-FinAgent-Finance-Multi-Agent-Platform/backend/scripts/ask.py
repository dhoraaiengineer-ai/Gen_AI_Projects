"""Ask FinAgent a question from the terminal, as a demo user (end-to-end through the real API).

Signs in with Supabase (publishable key + DEMO_USER_PASSWORD), calls POST /api/v1/chat/stream on
the running API and prints the live agent timeline and the final report.

Usage:
  uv run python -m scripts.ask "Why has the risk of Portfolio A increased?" [--user risk@northwind.example.com]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

from src.config.settings import get_settings


def sign_in(email: str) -> str:
    s = get_settings()
    if not (s.supabase_url and s.supabase_publishable_key and s.demo_user_password):
        raise SystemExit(
            "SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY and DEMO_USER_PASSWORD must be set"
        )
    response = httpx.post(
        f"{s.supabase_url.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": s.supabase_publishable_key.get_secret_value()},
        json={"email": email, "password": s.demo_user_password.get_secret_value()},
        timeout=20,
    )
    if response.status_code != 200:
        raise SystemExit(f"sign-in failed: HTTP {response.status_code} {response.text[:200]}")
    return str(response.json()["access_token"])


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("question")
    parser.add_argument("--user", default="risk@northwind.example.com")
    parser.add_argument("--api", default=f"http://127.0.0.1:{get_settings().api_port}")
    parser.add_argument("--json", action="store_true", help="print the full report JSON")
    args = parser.parse_args()
    token = sign_in(args.user)
    started = time.perf_counter()
    report = None
    with httpx.stream(
        "POST",
        f"{args.api}/api/v1/chat/stream",
        json={"question": args.question},
        headers={"Authorization": f"Bearer {token}"},
        timeout=180,
    ) as response:
        if response.status_code != 200:
            print(f"HTTP {response.status_code}: {response.read().decode()[:300]}")
            return 1
        tokens = False
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            kind = event.get("event")
            t = f"{time.perf_counter() - started:5.1f}s"
            if kind == "token":
                if not tokens:
                    print(f"{t}  narrative: ", end="")
                    tokens = True
                print(event["text"], end="", flush=True)
                continue
            if tokens:
                print()
                tokens = False
            if kind == "classification":
                print(
                    f"{t}  intent={event['intent']} via {event['method']} portfolio={event['portfolio']}"
                )
            elif kind == "plan":
                print(
                    f"{t}  plan: {' → '.join('+'.join(stage) for stage in event['stages']) or '(none)'}"
                )
            elif kind == "agent_start":
                print(f"{t}  ▶ {event['agent']} agent")
            elif kind == "agent_end":
                print(
                    f"{t}  ✓ {event['agent']} agent: {event['status']} conf={event['confidence']} "
                    f"tools={','.join(event['tools'])}"
                )
            elif kind == "report":
                report = event["report"]
            elif kind in ("error", "done", "start"):
                print(f"{t}  {kind} {event.get('message', '')}".rstrip())
    if report:
        print("\n" + "=" * 100)
        print("HEADLINE:", report["headline"])
        print(
            f"RISK LEVEL: {report['riskLevel']}   CONFIDENCE: {report['confidence']}   "
            f"APPROVAL REQUIRED: {report['approval']['required']}"
        )
        print("\nINTERPRETATION (" + report["sections"]["interpretationSource"] + "):")
        print(report["sections"]["interpretation"])
        print("\nFACTS:")
        for fact in report["sections"]["facts"]:
            print(f"  [{fact['agent']}] {fact['text']}")
        for title, key in (
            ("RECOMMENDATIONS", "recommendations"),
            ("ASSUMPTIONS", "assumptions"),
            ("UNCERTAINTY", "uncertainty"),
        ):
            if report["sections"][key]:
                print(f"\n{title}:")
                for item in report["sections"][key]:
                    print("  -", item)
        print("\n" + report["disclaimer"])
        if args.json:
            print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
