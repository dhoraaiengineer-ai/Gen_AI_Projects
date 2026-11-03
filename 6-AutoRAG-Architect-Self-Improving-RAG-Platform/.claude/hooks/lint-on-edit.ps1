# .claude/hooks/lint-on-edit.ps1
# AutoRAG v3.0 — Post-Edit Quality Hook
# Runs ruff + mypy (backend), ESLint (frontend), and prettier on recently modified files.
# Triggered by Claude Code PostToolUse (Write|Edit matcher in .claude/settings.json).

$ErrorActionPreference = "Continue"

Write-Host "Running AutoRAG post-edit quality check..." -ForegroundColor Cyan

# Get changed files from git working tree
try {
    $changedFiles = git diff --name-only 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git diff failed" }
} catch {
    Write-Host "Git not available or not a repository. Skipping." -ForegroundColor Yellow
    Exit 0
}

if ($null -eq $changedFiles -or $changedFiles.Count -eq 0) {
    Write-Host "No modified files detected." -ForegroundColor Green
    Exit 0
}

$pyFiles  = @($changedFiles | Where-Object { $_ -match '\.py$' })
$tsFiles  = @($changedFiles | Where-Object { $_ -match '\.(ts|tsx)$' })
$fmtFiles = @($changedFiles | Where-Object { $_ -match '\.(json|md|css|scss)$' })

# ── Python: ruff via uv run (preferred) or direct PATH ───────────────────────
if ($pyFiles.Count -gt 0) {
    Write-Host "Python files changed: $($pyFiles -join ', ')" -ForegroundColor Yellow

    $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
    $ruffAvailable = Get-Command ruff -ErrorAction SilentlyContinue

    if ($uvAvailable) {
        Write-Host "  uv run ruff format..." -ForegroundColor Gray
        uv run ruff format $pyFiles
        Write-Host "  uv run ruff check --fix..." -ForegroundColor Gray
        uv run ruff check --fix $pyFiles
        Write-Host "  Python lint: done" -ForegroundColor Green
    } elseif ($ruffAvailable) {
        Write-Host "  ruff format..." -ForegroundColor Gray
        ruff format $pyFiles
        Write-Host "  ruff check --fix..." -ForegroundColor Gray
        ruff check --fix $pyFiles
        Write-Host "  Python lint: done" -ForegroundColor Green
    } else {
        Write-Host "  ruff not found — run: uv sync --all-groups" -ForegroundColor Gray
    }
}

# ── TypeScript/TSX: ESLint via npm workspaces ────────────────────────────────
if ($tsFiles.Count -gt 0) {
    Write-Host "TypeScript files changed: $($tsFiles -join ', ')" -ForegroundColor Yellow

    $npmAvailable = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmAvailable) {
        Write-Host "  ESLint (npm run lint --workspace=autorag-client)..." -ForegroundColor Gray
        npm run lint --workspace=autorag-client 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ESLint: passed" -ForegroundColor Green
        } else {
            Write-Host "  ESLint: errors found — fix before committing" -ForegroundColor Red
        }
    } else {
        Write-Host "  npm not found — skipping ESLint" -ForegroundColor Gray
    }
}

# ── JSON / Markdown / CSS: prettier via npx ──────────────────────────────────
if ($fmtFiles.Count -gt 0) {
    Write-Host "Formatting files: $($fmtFiles -join ', ')" -ForegroundColor Yellow

    $npxAvailable = Get-Command npx -ErrorAction SilentlyContinue
    if ($npxAvailable) {
        npx prettier --write $fmtFiles 2>$null
        Write-Host "  Prettier: done" -ForegroundColor Green
    } else {
        Write-Host "  npx not found — skipping formatting" -ForegroundColor Gray
    }
}

Write-Host "Post-edit check complete." -ForegroundColor Cyan
