#!/usr/bin/env bash
# dev-setup.sh — AutoRAG v4.0 local dev bootstrap (Linux/macOS)
# Updated: 17-Jul-2026
set -euo pipefail

echo "AutoRAG Architect v4.0 — local dev bootstrap"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required (Node.js 20+). Install from https://nodejs.org" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required (Python package manager). Install from https://docs.astral.sh/uv/" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

# No .env.example template exists (removed 16-Jul-2026) -- team leads
# (Mahesh Kumar) distribute the real, pre-filled .env file directly.
# This script cannot create one for you; it can only verify it's present.
MISSING_ENV=0
for f in .env autorag-server/.env autorag-client/.env; do
  if [ ! -f "$f" ]; then
    echo "Missing: $f — get the real file from your lead, do not create your own." >&2
    MISSING_ENV=1
  fi
done
if [ "$MISSING_ENV" -eq 1 ]; then
  echo "See .claude/docs/setup.md for the full environment variable reference." >&2
  exit 1
fi

echo "Installing npm workspace dependencies (frontend)..."
npm install

echo "Installing backend Python dependencies (via uv)..."
cd autorag-server && uv sync --all-groups && cd ..

echo "Installing pre-commit hooks (lint + stack-sync run before every commit)..."
if command -v uv >/dev/null 2>&1; then
  uv run pre-commit install
else
  pre-commit install
fi

if command -v docker >/dev/null 2>&1; then
  echo "Starting local infrastructure (Redis)..."
  docker compose up -d redis
  echo "Redis (port 6379) started."
  echo "Note: the database is Supabase Cloud, not a local container — set SUPABASE_URL + SUPABASE_KEY"
  echo "      + DATABASE_URL in .env. A disposable local Postgres is available as an opt-in via"
  echo "      docker compose -f docker-compose.yml -f docker-compose.local.yml up -d — see"
  echo "      .claude/docs/docker-guide.md for when to use it (heavy-restart debugging sessions)."
else
  echo "Warning: Docker not found. Start Redis manually before running the backend." >&2
fi

echo ""
echo "✅ Setup complete. To start the project:"
echo "  Terminal 1 (backend):  cd autorag-server && uv run uvicorn app.main:app --reload"
echo "  Terminal 2 (frontend): npm run dev --workspace=autorag-client"
echo "  Or all at once:        npm run dev"
echo ""
echo "Verify everything is working:"
echo "  http://localhost:3000           — Next.js dashboard"
echo "  http://localhost:8000/health    — FastAPI health check"
echo "  http://localhost:8000/docs      — Swagger UI (46 endpoints)"
echo ""
echo "See .claude/docs/setup.md for the full setup guide."
