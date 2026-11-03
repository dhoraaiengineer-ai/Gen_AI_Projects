# check-api-contract.ps1 -- AutoRAG v4.0 API Contract Drift Checker (Windows/PowerShell)
# Regenerates autorag-client/types/generated-api.ts from the live backend's OpenAPI
# schema and diffs it against the committed version. Mirrors check-api-contract.sh.
#
# Requires the backend running locally (ENVIRONMENT=local) at $ApiBaseUrl.
# Run manually:  pwsh -File scripts/check-api-contract.ps1
#
# Added: 11-Jul-2026

param(
  [string]$ApiBaseUrl = "http://localhost:8001"
)

$root = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $root "autorag-client")

$committed = "types/generated-api.ts"
$tmp = New-TemporaryFile

Write-Host "AutoRAG v4.0 -- API Contract Drift Check (11-Jul-2026)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

try {
  Invoke-WebRequest -Uri "$ApiBaseUrl/health" -TimeoutSec 5 -UseBasicParsing | Out-Null
} catch {
  Write-Host "[SKIP] Backend not reachable at $ApiBaseUrl -- start it and re-run:" -ForegroundColor Yellow
  Write-Host "       cd autorag-server; `$env:ENVIRONMENT='local'; uv run uvicorn app.main:app --port 8001"
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  exit 0
}

npx --yes openapi-typescript "$ApiBaseUrl/openapi.json" -o $tmp.FullName 2>$null | Out-Null

if (-not (Test-Path $committed)) {
  Write-Host "[INFO] $committed does not exist yet -- generating it now."
  Copy-Item $tmp.FullName $committed -Force
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  Write-Host "[OK] Generated. Commit it." -ForegroundColor Green
  exit 0
}

$diff = Compare-Object (Get-Content $committed) (Get-Content $tmp.FullName)

if (-not $diff) {
  Write-Host "[OK] Frontend types match the live backend schema." -ForegroundColor Green
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  exit 0
} else {
  Write-Host "[FAIL] $committed is stale -- backend routes/schemas changed." -ForegroundColor Red
  Write-Host ""
  $diff | Select-Object -First 40 | Format-Table -AutoSize
  Write-Host ""
  Write-Host "Fix: cd autorag-client; npm run generate:api-types; commit the diff."
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  exit 1
}
