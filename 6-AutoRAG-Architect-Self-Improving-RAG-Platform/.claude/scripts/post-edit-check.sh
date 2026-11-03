#!/usr/bin/env bash
# AutoRAG v3.0 — Post-Edit Project Checks (bash)
# Used by CI on Linux runners (GitHub Actions).
# Uses UV for Python, npm for frontend.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Running AutoRAG post-edit checks..."

# ── Backend: ruff + mypy + pytest via uv ─────────────────────────────────────
if [ -d "$ROOT/autorag-server" ]; then
    echo "Backend checks..."

    if command -v uv &>/dev/null; then
        echo "  ruff check..."
        uv run --directory "$ROOT/autorag-server" ruff check app || { echo "  ruff: FAILED"; EXIT_CODE=1; }

        echo "  mypy..."
        uv run --directory "$ROOT/autorag-server" mypy app \
            --ignore-missing-imports \
            --config-file "$ROOT/autorag-server/pyproject.toml" || { echo "  mypy: FAILED"; EXIT_CODE=1; }

        echo "  pytest..."
        uv run --directory "$ROOT/autorag-server" pytest -q || { echo "  pytest: FAILED"; EXIT_CODE=1; }
    else
        echo "  uv not found — skipping backend checks"
    fi
fi

# ── Frontend: ESLint + type-check via npm workspaces ─────────────────────────
if [ -f "$ROOT/autorag-client/package.json" ]; then
    echo "Frontend checks..."

    if command -v npm &>/dev/null; then
        echo "  ESLint..."
        npm run lint --workspace=autorag-client || { echo "  ESLint: FAILED"; EXIT_CODE=1; }

        echo "  TypeScript type check..."
        npm run typecheck --workspace=autorag-client || { echo "  tsc: FAILED"; EXIT_CODE=1; }
    else
        echo "  npm not found — skipping frontend checks"
    fi
fi

echo "Post-edit checks complete."
exit "${EXIT_CODE:-0}"
