# check-stack-sync.ps1 — AutoRAG v4.0 Stack Drift Checker (Windows/PowerShell)
# Scans the project for banned old-stack terms that indicate stale v2.4 references.
# Exits 1 (blocks commit) if any are found outside of intentionally preserved files.
#
# Run manually:  pwsh -File scripts/check-stack-sync.ps1
# Runs via:      make sync-check
#
# Updated: 05-Jul-2026
# - Removed 'uv sync' from banned list (it is the correct install command)
# - Added Rule 86 governance terms: import boto3, from qdrant_client, import openai
# - Added 'trace_id' (must be 'x_trace_id' per all GraphState fields)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

# Terms that must NOT appear in active files (v2.4 stack / forbidden patterns)
$bannedTerms = @(
  'Presidio',
  'GPT-4o',
  'text-embedding-3-large',
  'pnpm install',
  'pnpm dev',
  'pnpm run',
  'import boto3',
  'from qdrant_client',
  'import openai',
  'trace_id'
)

# Paths intentionally preserved with old-stack references (excluded from scan)
$excludedPaths = @(
  '.claude\adr\002-gemini.md',
  '.claude\adr\005-supabase.md',
  'architecture\adr-index.md',
  'project_docs\AutoRAG_Architect_Architecture_Guide_v2.md',
  'project_docs\6_LLD\AutoRAG-LLD-v1.0.md',
  'project_docs\3_PRD\AutoRAG_PRD_v2_4.md',
  'mydocs\AutoRAG_Architect_Architecture_Guide_v2.md',
  'mydocs\Architecture_videos',
  'node_modules',
  '.git',
  '.venv',
  '.turbo',
  '__pycache__',
  'scripts\check-stack-sync'
)

$extensions = @('*.md','*.yml','*.yaml','*.py','*.ts','*.tsx','*.tf','*.sh','*.ps1')

$found = $false

Write-Host "AutoRAG v4.0 — Stack Sync Check (05-Jul-2026)" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

function Test-Excluded($filePath) {
  foreach ($excl in $excludedPaths) {
    if ($filePath -like "*$excl*") { return $true }
  }
  return $false
}

# Check banned terms
foreach ($term in $bannedTerms) {
  $hits = @()
  # Bare "trace_id" is banned, but x_trace_id (the correct, required field name
  # per Rule 86 / GraphState) contains "trace_id" as a substring -- a plain
  # escaped-literal match always false-positives on every legitimate
  # x_trace_id occurrence. Use a negative lookbehind for this term only.
  $searchPattern = if ($term -eq 'trace_id') { '(?<!x_)\btrace_id\b' } else { [regex]::Escape($term) }
  foreach ($ext in $extensions) {
    Get-ChildItem -Recurse -Filter $ext -ErrorAction SilentlyContinue | ForEach-Object {
      if (-not (Test-Excluded $_.FullName)) {
        $hitMatches = Select-String -Path $_.FullName -Pattern $searchPattern -ErrorAction SilentlyContinue
        if ($hitMatches) { $hits += $hitMatches }
      }
    }
  }
  if ($hits.Count -gt 0) {
    Write-Host ""
    Write-Host "❌ BANNED TERM FOUND: '$term'" -ForegroundColor Red
    $hits | ForEach-Object { Write-Host "   $($_.Filename):$($_.LineNumber)  $($_.Line.Trim())" -ForegroundColor Yellow }
    $found = $true
  }
}

# Special check: Qdrant outside of ADRs
$qdrantHits = @()
foreach ($ext in $extensions) {
  Get-ChildItem -Recurse -Filter $ext -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not (Test-Excluded $_.FullName)) {
      $hitMatches = Select-String -Path $_.FullName -Pattern 'Qdrant' -ErrorAction SilentlyContinue
      if ($hitMatches) { $qdrantHits += $hitMatches }
    }
  }
}
if ($qdrantHits.Count -gt 0) {
  Write-Host ""
  Write-Host "❌ BANNED TERM FOUND: 'Qdrant' (use 'Supabase Vector (pgvector)' instead)" -ForegroundColor Red
  $qdrantHits | ForEach-Object { Write-Host "   $($_.Filename):$($_.LineNumber)  $($_.Line.Trim())" -ForegroundColor Yellow }
  $found = $true
}

# Rule 86 governance: cost_usd must only be computed in llm_service.py
# Flag any Python file outside llm_service.py that multiplies tokens by a rate
$tokenCostPattern = 'prompt_tokens.*\*|completion_tokens.*\*|total_tokens.*\*'
$tokenCostHits = @()
Get-ChildItem -Recurse -Filter '*.py' -ErrorAction SilentlyContinue | ForEach-Object {
  if (-not (Test-Excluded $_.FullName) -and $_.Name -notlike 'llm_service*' -and $_.FullName -notlike '*test*') {
    $m = Select-String -Path $_.FullName -Pattern $tokenCostPattern -ErrorAction SilentlyContinue
    if ($m) { $tokenCostHits += $m }
  }
}
if ($tokenCostHits.Count -gt 0) {
  Write-Host ""
  Write-Host "⚠️  Rule 86 WARNING: Token cost arithmetic found outside llm_service.py" -ForegroundColor DarkYellow
  Write-Host "   Cost calculation must only happen in app/services/llm_service.py" -ForegroundColor DarkYellow
  $tokenCostHits | ForEach-Object { Write-Host "   $($_.Filename):$($_.LineNumber)  $($_.Line.Trim())" -ForegroundColor Yellow }
  $found = $true
}

Write-Host ""
if (-not $found) {
  Write-Host "✅ Stack sync PASSED — no stale v2.4 references or governance violations found." -ForegroundColor Green
  exit 0
} else {
  Write-Host "🚫 Stack sync FAILED — fix the above before committing." -ForegroundColor Red
  Write-Host "   Intentionally preserved files (ADRs, LLD, PRD) are excluded from this check." -ForegroundColor DarkCyan
  exit 1
}
