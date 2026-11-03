"""Shared pytest fixtures for autorag-server tests."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Set required env vars before any app module is imported.
# Settings validates DATABASE_URL and JWT_SECRET_KEY at class construction time.
# Using setdefault: real values in the environment always win.
# User/password here MUST match docker-compose.yml's local Postgres provisioning
# (POSTGRES_USER=postgres / POSTGRES_PASSWORD=postgres, root .env) -- that container
# never creates a "test" role, so a mismatched fallback here fails auth (13-Jul-2026 fix).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/autorag_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-key-minimum-32-characters-for-testing-only",
)
# V4 rate-limit pacing (26-Jul-2026): BatchEvalService.dispatch_batch_run
# sleeps BATCH_EVAL_SAMPLE_COOLDOWN_SECONDS (default 25s) between questions
# to avoid a free-tier judge provider 429ing -- zeroed here so tests that
# dispatch multiple batch_evaluations rows don't take minutes to run.
os.environ.setdefault("BATCH_EVAL_SAMPLE_COOLDOWN_SECONDS", "0")

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.document import ParsedPage  # noqa: E402
from app.services import guardrail_enforcement  # noqa: E402

# Dedicated NullPool test engine -- deliberately NOT the app's pooled
# `AsyncSessionLocal` singleton (app.core.database.engine), which is created once
# at import time and, under pytest-asyncio's per-test event loops, ends up with
# pooled asyncpg connections bound to a *different* test's (already-closed) loop.
# asyncpg connections are hard loop-affine (this is documented asyncpg behavior,
# not an AutoRAG bug); NullPool opens a fresh connection per checkout and closes
# it on release, so no connection ever survives across a test/loop boundary
# (13-Jul-2026 fix, found while live-verifying real-DB integration tests on
# Windows/Python 3.14 -- see verification/releases/v4.0/readiness/MVP_FINAL_READINESS_CHECKLIST.md).
_test_engine = create_async_engine(
    os.environ["DATABASE_URL"], poolclass=NullPool, pool_pre_ping=True
)
_TestSessionLocal = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = _override_get_db

# ──────────────────────────────────────────────────────────────
# Embedders (mock + real)
# ──────────────────────────────────────────────────────────────


class MockEmbedder:
    """Deterministic mock embedder — returns unique 768-dim vectors per text.

    Satisfies the Embedder Protocol: async def embed(text: str, x_trace_id: str).
    Seed is derived from text content so identical sentences get identical vectors —
    this allows the cosine similarity logic in chunkers to behave deterministically in tests.
    """

    async def embed(self, text: str, x_trace_id: str) -> list[float]:
        seed = abs(hash(text)) % 1000
        base = seed / 1000.0 + 0.01
        return [base] * 768


class RealEmbedder:
    """
    Self-contained EURI embedding client — no project-level dependencies.

    Uses EURI_API_KEY, EURI_BASE_URL, EURI_EMBEDDING_MODEL from environment.
    EURI endpoint is OpenAI-compatible: POST {base}/embeddings
    Satisfies the Embedder Protocol: async def embed(text: str, x_trace_id: str).
    """

    def __init__(self) -> None:
        self._api_key = os.environ["EURI_API_KEY"]
        base_url = os.environ.get("EURI_BASE_URL", "https://api.euron.one/api/v1/euri")
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._model = os.environ.get("EURI_EMBEDDING_MODEL", "gemini-embedding-2")

    async def embed(self, text: str, x_trace_id: str) -> list[float]:
        """Embed a single text via EURI OpenAI-compatible embeddings endpoint."""
        import httpx as _httpx

        async with _httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url,
                json={"input": [text], "model": self._model},
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        data: list[dict[str, Any]] = body["data"]
        return data[0]["embedding"]


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Windows' default ProactorEventLoop can't finish asyncpg's connection-close
    cancellation task after pytest-asyncio closes the per-test event loop, surfacing
    as "RuntimeError: Event loop is closed" during teardown of any real-DB test.
    SelectorEventLoop doesn't have this asyncpg incompatibility (13-Jul-2026 fix).
    pytest-asyncio 1.x reads this fixture, not a module-level set_event_loop_policy()
    call, to pick the policy used for each test's event loop.
    """
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session")
def embedder() -> MockEmbedder | RealEmbedder:
    """
    Returns MockEmbedder by default.
    Set USE_REAL_EMBEDDINGS=1 to use real EURI API calls.

    Usage:
        uv run pytest -q                                  # mock (default)
        USE_REAL_EMBEDDINGS=1 uv run pytest -q            # real EURI API
    """
    if os.getenv("USE_REAL_EMBEDDINGS") == "1":
        yield RealEmbedder()
    else:
        yield MockEmbedder()


# ──────────────────────────────────────────────────────────────
# Test data fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sample_page() -> ParsedPage:
    """Load the synthetic sample document fixture."""
    path = Path(__file__).parent / "fixtures" / "sample_document.txt"
    return ParsedPage(
        page_number=1,
        content=path.read_text(),
        source_uri="s3://test-bucket/sample-doc.pdf",
    )


# ──────────────────────────────────────────────────────────────
# HTTP client fixtures
# ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Real PostgreSQL session — rolls back after each test (Rule 80).

    Uses the NullPool `_TestSessionLocal` (not the app's pooled singleton) so this
    fixture's connection can never be a stale pooled connection left over from a
    prior test's now-closed event loop.
    """
    async with _TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def _guardrail_enforcement_uses_test_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect `enforce_cost_guardrail`'s audit-log session to the NullPool test engine.

    `enforce_cost_guardrail` (app/services/guardrail_enforcement.py) imports
    `AsyncSessionLocal` from `app.core.database` at module load time and calls it
    directly -- the app's real pooled engine, not the `db_session` fixture's
    NullPool `_TestSessionLocal`. That pool is created once at import time; under
    pytest-asyncio's per-test event loops, a connection checked out by an earlier
    test stays bound to that test's (now-closed) loop, and reusing it from a later
    test's loop raises an asyncpg cross-loop error. `enforce_cost_guardrail`
    intentionally swallows that error (an audit-log failure must not mask the real
    guardrail block -- see its own `except Exception` comment), which surfaced as
    a real, reproducible flake under full-suite runs: `CostLimitExceeded` still
    raised correctly, but the audit row was silently never written.

    Disposing the pooled engine between tests was tried and made things worse (the
    disposal itself raced the closing per-test event loop). The correct fix is the
    one already proven for `db_session` above: never let this code path touch the
    pooled engine during tests at all. Monkeypatching the name as it exists in
    `guardrail_enforcement`'s own namespace (not `app.core.database.AsyncSessionLocal`,
    which `enforce_cost_guardrail` never looks up again after import) redirects it
    to the same NullPool session every other real-DB test already uses safely
    (13-Jul-2026 fix).
    """
    monkeypatch.setattr(guardrail_enforcement, "AsyncSessionLocal", _TestSessionLocal)
