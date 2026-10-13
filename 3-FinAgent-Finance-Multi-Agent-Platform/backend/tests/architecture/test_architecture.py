"""Architecture rules, enforced statically (AST) so they hold as the codebase grows.

1. Provider SDKs are imported only in the composition root and src/providers/ (ADR-022).
2. SQL (drivers, SQLAlchemy, raw statements) lives only in src/db and src/data.
3. src/services is pure: no I/O, frameworks, LLMs or other app layers.
4. Routes are thin: src/api never imports src/db or SQL drivers.
5. Agents never import each other; they talk through A2A.
6. Every HTTP route requires auth, except a deliberate, documented public list.
7. Every APIRouter declares a prefix.
8. Text file I/O always passes encoding= (Windows defaults to cp1252).
9. No secrets in tracked files; .env stays git-ignored.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute

from src.api.main import create_app

ROOT = Path(__file__).resolve().parents[2]  # backend/
REPO = ROOT.parent
SRC = ROOT / "src"

PROVIDER_SDKS = {
    "openai",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_aws",
    "anthropic",
    "boto3",
    "tiktoken",
    "redis",
    "tavily",
    "pytesseract",
    "pypdfium2",
    "sentence_transformers",
    "torch",
}
PROVIDER_ALLOWED_FILES = {SRC / "container.py"}
PROVIDER_ALLOWED_DIRS = {SRC / "providers"}

SQL_MODULES = {"sqlalchemy", "psycopg", "psycopg_pool", "asyncpg", "alembic", "pgvector"}
SQL_ALLOWED_DIRS = {SRC / "db", SRC / "data"}
SQL_STATEMENT = re.compile(
    r"^\s*(SELECT\s.+\sFROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+TABLE)\b",
    re.DOTALL | re.IGNORECASE,
)

SERVICES_FORBIDDEN = {
    "fastapi",
    "starlette",
    "httpx",
    "requests",
    "langchain",
    "langchain_core",
    "langgraph",
    "openai",
    "redis",
    "sqlalchemy",
    "psycopg",
    "mlflow",
    "src.db",
    "src.data",
    "src.api",
    "src.agents",
    "src.orchestration",
    "src.tools",
    "src.rag",
    "src.container",
    "src.mcp",
    "src.a2a",
    "src.ml",
}

# Public routes are deliberate exceptions. Each needs a reason.
PUBLIC_ROUTES: dict[str, str] = {
    "/health": "liveness probe for Docker/Kubernetes/ALB; returns no data",
    "/health/ready": "readiness probe; returns dependency status only, no data",
    "/docs": "FastAPI OpenAPI UI (disabled in production in Stage 8)",
    "/docs/oauth2-redirect": "FastAPI OpenAPI UI helper",
    "/redoc": "FastAPI ReDoc UI (disabled in production in Stage 8)",
    "/openapi.json": "OpenAPI schema (disabled in production in Stage 8)",
    "/api/v1/config/public": "frontend bootstrap: Supabase URL + publishable key; no secrets",
    "/metrics": "Prometheus scrape; not published outside the cluster network",
}

SECRET_PATTERNS = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9_\-]{10,}"
    r"|tvly-[A-Za-z0-9\-]{20,}|euri-[a-f0-9]{32,}|AIza[0-9A-Za-z_\-]{30,}"
    r"|AQ\.[A-Za-z0-9_\-]{30,}|AKIA[0-9A-Z]{16}"
    r"|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.)"
)
SECRET_SCAN_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".ts",
    ".tsx",
    ".js",
    ".txt",
    ".tf",
    ".cfg",
    ".ini",
    ".sh",
    ".ps1",
    ".example",
}
SKIP_DIRS = {".venv", ".git", "node_modules", ".next", "__pycache__", ".ruff_cache", ".mypy_cache"}


def _py_files(base: Path) -> Iterator[Path]:
    for path in base.rglob("*.py"):
        if not SKIP_DIRS.intersection(path.parts):
            yield path


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> Iterator[tuple[str, int]]:
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module, node.lineno


def _matches(module: str, roots: set[str]) -> bool:
    return any(module == r or module.startswith(r + ".") for r in roots)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _report(title: str, violations: list[str]) -> str:
    return f"{title}:\n" + "\n".join(violations)


def test_provider_sdks_only_in_composition_root() -> None:
    violations = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _py_files(SRC)
        if p not in PROVIDER_ALLOWED_FILES and not PROVIDER_ALLOWED_DIRS.intersection(p.parents)
        for mod, line in _imports(p)
        if _matches(mod, PROVIDER_SDKS)
    ]
    assert not violations, _report("Provider SDK outside the composition root", violations)


def test_sql_only_in_db_and_data() -> None:
    violations: list[str] = []
    for p in _py_files(SRC):
        if any(d in p.parents for d in SQL_ALLOWED_DIRS):
            continue
        violations += [
            f"{_rel(p)}:{line} imports {mod}"
            for mod, line in _imports(p)
            if _matches(mod, SQL_MODULES)
        ]
        violations += [
            f"{_rel(p)}:{n.lineno} raw SQL string"
            for n in ast.walk(_tree(p))
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and SQL_STATEMENT.match(n.value)
        ]
    assert not violations, _report("SQL outside src/db and src/data", violations)


def test_services_are_pure() -> None:
    violations = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _py_files(SRC / "services")
        for mod, line in _imports(p)
        if _matches(mod, SERVICES_FORBIDDEN)
    ]
    assert not violations, _report("src/services must stay pure", violations)


def test_api_does_not_touch_db_directly() -> None:
    violations = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _py_files(SRC / "api")
        for mod, line in _imports(p)
        if _matches(mod, {"src.db", "src.data", *SQL_MODULES})
    ]
    assert not violations, _report("Routes must go through the container", violations)


def test_agents_do_not_import_each_other() -> None:
    agents_dir = SRC / "agents"
    violations: list[str] = []
    for agent in (d for d in agents_dir.iterdir() if d.is_dir() and d.name != "__pycache__"):
        others = {f"src.agents.{o.name}" for o in agents_dir.iterdir() if o.is_dir()} - {
            f"src.agents.{agent.name}"
        }
        violations += [
            f"{_rel(p)}:{line} imports {mod}"
            for p in _py_files(agent)
            for mod, line in _imports(p)
            if _matches(mod, others)
        ]
    assert not violations, _report("Agents must talk via A2A, not imports", violations)


def _api_routes(routes: list[Any]) -> Iterator[Any]:
    """Yield every API route with its full path and effective dependant.

    FastAPI >= 0.140 wraps included routers in ``_IncludedRouter``; its
    ``effective_route_contexts()`` yields contexts carrying the combined prefix and the
    router- and include-level dependencies. Plain ``APIRoute`` objects are yielded as-is.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_route_contexts"):
            yield from (
                c
                for c in route.effective_route_contexts()
                if isinstance(c.original_route, APIRoute)
            )


def _dependency_calls(route: Any) -> Iterator[object]:
    stack = list(route.dependant.dependencies) if route.dependant else []
    while stack:
        dep = stack.pop()
        if dep.call is not None:
            yield dep.call
        stack.extend(dep.dependencies)


def _is_auth_guard(call: object) -> bool:
    return getattr(call, "__name__", "") == "require_user" or hasattr(call, "required_role")


def test_every_route_requires_auth_or_is_documented_public() -> None:
    routes = list(_api_routes(create_app().routes))
    # Guard against a vacuous pass (e.g. a FastAPI change hiding included routes).
    assert "/health" in {r.path for r in routes}, "route discovery found no application routes"
    unguarded = [
        f"{','.join(sorted(r.methods or []))} {r.path}"
        for r in routes
        if r.path not in PUBLIC_ROUTES and not any(_is_auth_guard(c) for c in _dependency_calls(r))
    ]
    assert not unguarded, _report(
        "Routes without require_user/require_role (add a guard or a reasoned PUBLIC_ROUTES entry)",
        unguarded,
    )


def test_routers_declare_a_prefix() -> None:
    violations = [
        f"{_rel(p)}:{node.lineno}"
        for p in _py_files(SRC / "api")
        for node in ast.walk(_tree(p))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", getattr(node.func, "attr", None)) == "APIRouter"
        and not any(k.arg == "prefix" for k in node.keywords)
    ]
    assert not violations, _report("APIRouter(...) without prefix=", violations)


def _text_io_violation(node: ast.Call) -> str | None:
    name = getattr(node.func, "attr", getattr(node.func, "id", None))
    kwargs = {k.arg for k in node.keywords}
    if "encoding" in kwargs:
        return None
    if name in {"read_text", "write_text"}:
        return f"{name}() without encoding="
    if name == "open":
        mode = node.args[1] if len(node.args) > 1 else None
        mode = mode or next((k.value for k in node.keywords if k.arg == "mode"), None)
        if not (isinstance(mode, ast.Constant) and "b" in str(mode.value)):
            return "open() without encoding="
    return None


def _awaited(tree: ast.AST) -> set[int]:
    return {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Await)}


@pytest.mark.parametrize("base", ["src", "scripts", "tests"])
def test_text_io_passes_encoding(base: str) -> None:
    violations = [
        f"{_rel(p)}:{node.lineno} {msg}"
        for p in _py_files(ROOT / base)
        for tree in [_tree(p)]
        for awaited in [_awaited(tree)]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and id(node) not in awaited  # awaited .open() = pools/clients, not file I/O
        and (msg := _text_io_violation(node))
    ]
    assert not violations, _report("Text I/O must pass encoding=", violations)


def test_no_secrets_in_tracked_files() -> None:
    hits: list[str] = []
    for p in ROOT.rglob("*"):
        if (
            p.is_file()
            and (p.suffix in SECRET_SCAN_SUFFIXES or p.name == ".env.example")
            and not SKIP_DIRS.intersection(p.parts)
            and p.name != ".env"
            and not (p.name.startswith(".env.") and p.name != ".env.example")
        ):
            for i, line in enumerate(
                p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if SECRET_PATTERNS.search(line):
                    hits.append(f"{_rel(p)}:{i}")
    assert not hits, _report("Possible secrets (move them to .env)", hits)


def test_env_file_is_git_ignored() -> None:
    patterns = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in patterns
    assert ".env.*" in patterns
    assert "!.env.example" in patterns


ROUTE_ALLOWED = {
    "src.api",
    "src.presenters",
    "src.schemas",
    "src.security",
    "src.container",
    "src.core.domain",
}


def test_routes_are_thin_views() -> None:
    """MVP (ADR-025): routes import presenters, schemas and auth only — no domain logic."""
    violations = [
        f"{_rel(p)}:{line} imports {mod}"
        for p in _py_files(SRC / "api" / "routes")
        for mod, line in _imports(p)
        if mod.startswith("src.") and not _matches(mod, ROUTE_ALLOWED)
    ]
    assert not violations, _report("Routes may only use presenters/schemas/security", violations)
