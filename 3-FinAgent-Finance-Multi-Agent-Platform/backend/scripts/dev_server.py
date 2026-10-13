"""Windows-compatible dev server: one worker on port 8020 with a Selector event loop.

Async psycopg cannot run on the Proactor loop, which uvicorn picks on Windows unless it runs in a
reload subprocess. Without ``--reload`` we drive ``uvicorn.Server`` ourselves on a
SelectorEventLoop; with ``--reload`` uvicorn's subprocess already uses one.

Usage: uv run python -m scripts.dev_server [--reload] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn

from src.config.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    port = get_settings().api_port
    if args.reload:
        uvicorn.run("src.api.main:app", host=args.host, port=port, reload=True, log_config=None)
        return
    config = uvicorn.Config(
        "src.api.main:app", host=args.host, port=port, workers=1, log_config=None
    )
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
