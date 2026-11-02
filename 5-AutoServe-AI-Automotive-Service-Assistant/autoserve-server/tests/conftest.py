"""Test isolation + a seeded real-Postgres fixture for integration/security tests.

Unit tests never load the developer's .env (real keys / Supabase). DB tests need TEST_DATABASE_URL pointing at a
database whose name ends in `_test`; it is wiped, migrated, and seeded once per session.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx
import pytest

from app.core import config

config.Settings.model_config["env_file"] = None
os.environ.setdefault("APP_ENV", "ci")
for _var in ("DATABASE_URL", "EURI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "TAVILY_API_KEY", "TYPESAFE_API_KEY"):
    os.environ.pop(_var, None)
config.get_settings.cache_clear()

SERVER_DIR = Path(__file__).resolve().parents[1]
TEST_JWT_SECRET = "test-only-secret-" + "x" * 40
DEMO_PASSWORD = "Veloxa-Demo-2026!"  # matches scripts/seed.py default (synthetic)


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """psycopg async (LangGraph PostgresSaver) cannot run on Windows' default Proactor loop."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined,no-any-return]
    return asyncio.DefaultEventLoopPolicy()


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _reset_database(url: str) -> None:
    parts = urlsplit(_plain(url))
    db_name = parts.path.lstrip("/")
    admin_url = urlunsplit(parts._replace(path="/postgres"))
    admin = await asyncpg.connect(admin_url)
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name):
            await admin.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(_plain(url))
    try:
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


def _run(module_args: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(  # noqa: S603 — fixed interpreter + fixed module args
        [sys.executable, *module_args], cwd=SERVER_DIR, env=env, capture_output=True, text=True, timeout=300
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{module_args} failed:\n{proc.stdout}\n{proc.stderr}")


@pytest.fixture(scope="session")
def seeded_db() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set (provided by CI / compose) — P1-1")
    if not urlsplit(_plain(url)).path.rstrip("/").endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must point at a database whose name ends with '_test' (it gets wiped).")
    asyncio.run(_reset_database(url))
    env = {
        **os.environ,
        "DATABASE_URL": url if "+asyncpg" in url else url.replace("postgresql://", "postgresql+asyncpg://"),
        "DATABASE_URL_MIGRATIONS": _plain(url),
        "DATABASE_POOLER_MODE": "direct",
        "JWT_SECRET": TEST_JWT_SECRET,
        "SEED_DEMO_PASSWORD": DEMO_PASSWORD,
    }
    _run(["-m", "alembic", "upgrade", "head"], env)
    _run(["-m", "scripts.seed"], env)
    os.environ.update(
        {
            "DATABASE_URL": env["DATABASE_URL"],
            "DATABASE_POOLER_MODE": "direct",
            "DB_USE_NULL_POOL": "true",
            "AUTH_MODE": "demo",
            "JWT_SECRET": TEST_JWT_SECRET,
        }
    )
    config.get_settings.cache_clear()
    from app.core.db import reset_db_caches

    reset_db_caches()
    return url


@pytest.fixture
async def api(seeded_db: str) -> AsyncIterator[httpx.AsyncClient]:
    from app.core.security import login_limiter
    from app.main import create_app

    login_limiter.reset()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


LoginFn = Callable[[str], Awaitable[dict[str, str]]]


@pytest.fixture
def login(api: httpx.AsyncClient) -> LoginFn:
    async def _login(email: str) -> dict[str, str]:
        resp = await api.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}

    return _login


@pytest.fixture
async def db_conn(seeded_db: str) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_plain(seeded_db))
    try:
        yield conn
    finally:
        await conn.close()


# ── corpus ingested with the offline HashingEmbedder (shared by RAG / chat integration tests) ──
async def _ingest(root: Path) -> object:
    from app.core.db import get_sessionmaker
    from app.rag.embeddings import HashingEmbedder
    from app.rag.ingest import ingest_corpus

    async with get_sessionmaker()() as s, s.begin():
        return await ingest_corpus(s, HashingEmbedder(), root)


@pytest.fixture(scope="session")
def ingested(seeded_db: str, tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    from scripts.generate_knowledge import build

    root = tmp_path_factory.mktemp("corpus")
    build(root)
    first = asyncio.run(_ingest(root))
    second = asyncio.run(_ingest(root))
    return {"root": root, "first": first, "second": second}
