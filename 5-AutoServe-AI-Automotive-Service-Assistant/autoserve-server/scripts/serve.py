"""Run the API locally with a selector event loop (psycopg async / LangGraph PostgresSaver need it on Windows).

uvicorn ≥ 0.36 always picks the Proactor loop on Windows; with loop="none" it uses asyncio's default policy, which
`use_selector_loop()` sets. Docker/Linux is unaffected (selector loop by default).

Usage (from autoserve-server/): uv run python -m scripts.serve [--port 8011]
"""

from __future__ import annotations

import argparse
import asyncio

import uvicorn

from app.graph.workflow import use_selector_loop


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    use_selector_loop()
    server = uvicorn.Server(uvicorn.Config("app.main:app", host=args.host, port=args.port, loop="none"))
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
