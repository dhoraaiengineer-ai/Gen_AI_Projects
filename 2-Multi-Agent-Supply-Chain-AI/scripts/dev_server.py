"""Run the API locally without Docker (handles the Windows event-loop requirement of async psycopg).

    uv run python scripts/dev_server.py        # http://localhost:8000  (docs at /docs)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("APP_NO_AUTOCREATE", "1")

import uvicorn

from app.core.compat import use_compatible_event_loop


def main() -> None:
    use_compatible_event_loop()
    from app.main import create_app

    config = uvicorn.Config(create_app(), host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), loop="none", log_config=None)
    asyncio.run(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
