# dev-setup.ps1 — AutoRAG v4.0 local dev bootstrap (Windows/PowerShell)
# Updated: 17-Jul-2026
$ErrorActionPreference = "Stop"

Write-Host "AutoRAG Architect v4.0 — local dev bootstrap" -ForegroundColor Cyan

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Error "npm is required (Node.js 20+). Install from https://nodejs.org"
  exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Error "uv is required (Python package manager). Install from https://docs.astral.sh/uv/"
  Write-Host "  Run: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"" -ForegroundColor Yellow
  exit 1
}

# No .env.example template exists (removed 16-Jul-2026) -- team leads
# (Mahesh Kumar) distribute the real, pre-filled .env file directly.
# This script cannot create one for you; it can only verify it's present.
$missingEnv = $false
foreach ($f in @(".env", "autorag-server/.env", "autorag-client/.env")) {
  if (-not (Test-Path $f)) {
    Write-Warning "Missing: $f — get the real file from your lead, do not create your own."
    $missingEnv = $true
  }
}
if ($missingEnv) {
  Write-Host "See .claude/docs/setup.md for the full environment variable reference." -ForegroundColor Yellow
  exit 1
}

Write-Host "Installing npm workspace dependencies (frontend)..." -ForegroundColor Yellow
npm install

Write-Host "Installing backend Python dependencies (via uv)..." -ForegroundColor Yellow
Push-Location autorag-server
uv sync --all-groups
Pop-Location

Write-Host "Installing pre-commit hooks (lint + stack-sync run before every commit)..." -ForegroundColor Yellow
if (Get-Command uv -ErrorAction SilentlyContinue) {
  uv run pre-commit install
} else {
  pre-commit install
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
  Write-Host "Starting local infrastructure (Redis)..." -ForegroundColor Yellow
  docker compose up -d redis
  Write-Host "Redis (port 6379) started." -ForegroundColor Green
  Write-Host "Note: the database is Supabase Cloud, not a local container — set SUPABASE_URL + SUPABASE_KEY" -ForegroundColor DarkCyan
  Write-Host "      + DATABASE_URL in .env. A disposable local Postgres is available as an opt-in via" -ForegroundColor DarkCyan
  Write-Host "      docker compose -f docker-compose.yml -f docker-compose.local.yml up -d — see" -ForegroundColor DarkCyan
  Write-Host "      .claude/docs/docker-guide.md for when to use it (heavy-restart debugging sessions)." -ForegroundColor DarkCyan
} else {
  Write-Warning "Docker not found. Start Redis manually before running the backend."
}

Write-Host ""
Write-Host "✅ Setup complete. To start the project:" -ForegroundColor Cyan
Write-Host "  Terminal 1 (backend):  cd autorag-server; uv run uvicorn app.main:app --reload"
Write-Host "  Terminal 2 (frontend): npm run dev --workspace=autorag-client"
Write-Host "  Or all at once:        npm run dev"
Write-Host ""
Write-Host "Verify everything is working:" -ForegroundColor Cyan
Write-Host "  http://localhost:3000           — Next.js dashboard"
Write-Host "  http://localhost:8000/health    — FastAPI health check"
Write-Host "  http://localhost:8000/docs      — Swagger UI (46 endpoints)"
Write-Host ""
Write-Host "See .claude/docs/setup.md for the full setup guide." -ForegroundColor DarkCyan
