# AutoRAG v3.0 — Post-Edit Project Checks (PowerShell)
# Used by CI on Windows runners and optionally invoked manually.
# Uses UV for Python, npm for frontend.

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent

Write-Host "Running AutoRAG post-edit checks..." -ForegroundColor Cyan

# ── Backend: ruff + mypy + pytest via uv ─────────────────────────────────────
if (Test-Path "$root\autorag-server") {
    Write-Host "Backend checks..." -ForegroundColor Yellow

    $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvAvailable) {
        Write-Host "  ruff check..." -ForegroundColor Gray
        uv run --directory "$root\autorag-server" ruff check app
        if ($LASTEXITCODE -ne 0) { Write-Host "  ruff: FAILED" -ForegroundColor Red }

        Write-Host "  mypy..." -ForegroundColor Gray
        uv run --directory "$root\autorag-server" mypy app --ignore-missing-imports --config-file "$root\autorag-server\pyproject.toml"
        if ($LASTEXITCODE -ne 0) { Write-Host "  mypy: FAILED" -ForegroundColor Red }

        Write-Host "  pytest..." -ForegroundColor Gray
        uv run --directory "$root\autorag-server" pytest -q
        if ($LASTEXITCODE -ne 0) { Write-Host "  pytest: FAILED" -ForegroundColor Red }
    } else {
        Write-Host "  uv not found — skipping backend checks" -ForegroundColor Gray
    }
}

# ── Frontend: ESLint + type-check via npm workspaces ─────────────────────────
if (Test-Path "$root\autorag-client\package.json") {
    Write-Host "Frontend checks..." -ForegroundColor Yellow

    $npmAvailable = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmAvailable) {
        Write-Host "  ESLint..." -ForegroundColor Gray
        npm run lint --workspace=autorag-client
        if ($LASTEXITCODE -ne 0) { Write-Host "  ESLint: FAILED" -ForegroundColor Red }

        Write-Host "  TypeScript type check..." -ForegroundColor Gray
        npm run typecheck --workspace=autorag-client
        if ($LASTEXITCODE -ne 0) { Write-Host "  tsc: FAILED" -ForegroundColor Red }
    } else {
        Write-Host "  npm not found — skipping frontend checks" -ForegroundColor Gray
    }
}

Write-Host "Post-edit checks complete." -ForegroundColor Cyan
