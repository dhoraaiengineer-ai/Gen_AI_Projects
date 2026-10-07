"""Architecture rules enforced as tests.

Provider-specific SDKs may only be imported by the composition root, so every other module depends on
interfaces and can be tested with fakes.
"""

import ast
from pathlib import Path

import app

APP_DIR = Path(app.__file__).parent

# module prefix -> files (relative to app/) or directories allowed to import it
RESTRICTED_IMPORTS: dict[str, tuple[str, ...]] = {
    "openai": ("rag/providers.py", "container.py"),
    "langchain_openai": ("rag/providers.py", "container.py"),
    "redis": ("rag/providers.py", "container.py"),
    "tavily": ("rag/providers.py", "container.py"),
    "langchain_postgres": ("rag/providers.py", "container.py"),
    "pytesseract": ("rag/providers.py", "container.py"),
    "psycopg": ("db/", "rag/providers.py", "container.py"),
    "sqlalchemy": ("db/", "rag/providers.py", "container.py"),
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _is_allowed(rel_path: str, allowed: tuple[str, ...]) -> bool:
    return any(rel_path == a or (a.endswith("/") and rel_path.startswith(a)) for a in allowed)


def test_provider_sdks_are_only_imported_by_the_composition_root() -> None:
    violations: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        rel = path.relative_to(APP_DIR).as_posix()
        for module in _imported_modules(path):
            root = module.split(".")[0]
            allowed = RESTRICTED_IMPORTS.get(root)
            if allowed is not None and not _is_allowed(rel, allowed):
                violations.append(f"app/{rel} imports {module}")
    assert not violations, "Provider imports outside the composition root:\n" + "\n".join(violations)


def test_package_exposes_version() -> None:
    assert app.__version__
