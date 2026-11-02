# AutoServe AI — Windows equivalent of the Makefile. Usage: .\dev.ps1 <target>
param([Parameter(Position = 0)][string]$Target = "help")

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Server = Join-Path $Root "autoserve-server"
$Client = Join-Path $Root "autoserve-client"

function Invoke-In([string]$Dir, [scriptblock]$Block) {
    Push-Location $Dir
    try { & $Block; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
}

function Not-Yet([string]$Name, [string]$Task) {
    Write-Host "${Name}: not implemented yet (task $Task)"
    exit 1
}

switch ($Target) {
    "install"      { Invoke-In $Server { uv sync }; Invoke-In $Client { npm ci } }
    "up"           { docker compose up -d --build }
    "down"         { docker compose down }
    "logs"         { docker compose logs -f --tail=100 }
    "migrate"      { Invoke-In $Server { uv run alembic upgrade head } }
    "seed"         { Invoke-In $Server { uv run python -m scripts.seed } }
    "ingest"       { Invoke-In $Server { uv run python -m scripts.ingest } }
    "test"         {
        Invoke-In $Server { uv run pytest -q --cov --cov-report=term-missing:skip-covered }
        Invoke-In $Client { npm run test }
    }
    "lint"         {
        Invoke-In $Server { uv run ruff check .; if ($LASTEXITCODE -eq 0) { uv run ruff format --check . }; if ($LASTEXITCODE -eq 0) { uv run mypy } }
        Invoke-In $Client { npm run lint; if ($LASTEXITCODE -eq 0) { npm run typecheck } }
    }
    "eval"         { Not-Yet "eval" "P1-7" }
    "demo"         { Not-Yet "demo" "P5-2" }
    "check-models" { Invoke-In $Server { uv run python -m scripts.check_models } }
    default        { Write-Host "Targets: install up down logs migrate seed ingest test lint eval demo check-models" }
}
