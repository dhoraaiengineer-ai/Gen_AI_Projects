"""Platform compatibility. psycopg's async mode can't use Windows' default Proactor event loop.

Containers run Linux, so this only matters for local scripts and tests on Windows.
"""

from __future__ import annotations

import asyncio
import sys


def use_compatible_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
