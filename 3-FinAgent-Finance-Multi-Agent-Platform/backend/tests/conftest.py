"""Test-wide setup. Tests run offline and must never read the developer's .env."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

# Settings read this flag and skip the .env file under test.
os.environ.setdefault("FINAGENT_TESTING", "1")


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Async psycopg cannot run on Windows' Proactor loop (DB integration tests)."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined,unused-ignore]
    return asyncio.DefaultEventLoopPolicy()
