#!/usr/bin/env bash
# check-stack-sync.sh — AutoRAG v4.0 Stack Drift Checker
# Scans the project for banned old-stack terms that indicate stale v2.4 references.
# Exits 1 (blocks commit) if any are found outside of intentionally preserved files.
#
# Run manually:  bash scripts/check-stack-sync.sh
# Runs via:      make sync-check
#                git pre-commit hook (via .pre-commit-config.yaml)
#
# Updated: 05-Jul-2026
# - Removed 'uv sync' from banned list (it is the correct install command)
# - Removed redundant --exclude-dir grep flags (path filter loop is authoritative)
# - Added Rule 86 governance term: 'agent_metrics' GraphState key

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Terms that must NOT appear in active files (v2.4 stack / forbidden patterns)
BANNED_TERMS=(
  "Presidio"
  "GPT-4o"
  "text-embedding-3-large"
  "pnpm install"
  "pnpm dev"
  "pnpm run"
  "import boto3"
  "from qdrant_client"
  "import openai"
  "trace_id"
)

# Files/paths intentionally preserved with old-stack references (excluded from scan)
EXCLUDE_PATTERNS=(
  ".claude/adr/002-gemini.md"
  ".claude/adr/005-supabase.md"
  "architecture/adr-index.md"
  "project_docs/AutoRAG_Architect_Architecture_Guide_v2.md"
  "project_docs/6_LLD/AutoRAG-LLD-v1.0.md"
  "project_docs/3_PRD/AutoRAG_PRD_v2_4.md"
  "mydocs/AutoRAG_Architect_Architecture_Guide_v2.md"
  "mydocs/Architecture_videos/"
  "node_modules/"
  ".git/"
  "scripts/check-stack-sync.sh"
  "scripts/check-stack-sync.ps1"
)

FOUND=0

echo "AutoRAG v4.0 — Stack Sync Check (05-Jul-2026)"
echo "==============================================="

for term in "${BANNED_TERMS[@]}"; do
  if [ "$term" = "trace_id" ]; then
    # Bare "trace_id" is banned, but x_trace_id (the correct, required field
    # name per Rule 86 / GraphState) contains "trace_id" as a substring --
    # without a negative-lookbehind-equivalent this always false-positives on
    # every one of the hundreds of legitimate x_trace_id occurrences. grep
    # -P supports \b(?<!x_)trace_id\b (Perl regex); GNU grep on Linux/macOS
    # ships with -P support.
    results=$(grep -rnP \
      --include="*.md" --include="*.yml" --include="*.yaml" \
      --include="*.py" --include="*.ts" --include="*.tsx" \
      --include="*.tf" --include="*.sh" --include="*.ps1" \
      --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv \
      --exclude-dir=.turbo --exclude-dir=__pycache__ \
      '(?<!x_)\btrace_id\b' . 2>/dev/null || true)
  else
    results=$(grep -rn \
      --include="*.md" --include="*.yml" --include="*.yaml" \
      --include="*.py" --include="*.ts" --include="*.tsx" \
      --include="*.tf" --include="*.sh" --include="*.ps1" \
      --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv \
      --exclude-dir=.turbo --exclude-dir=__pycache__ \
      "$term" . 2>/dev/null || true)
  fi

  filtered=""
  while IFS= read -r line; do
    skip=false
    for excl in "${EXCLUDE_PATTERNS[@]}"; do
      if [[ "$line" == *"$excl"* ]]; then
        skip=true
        break
      fi
    done
    if [ "$skip" = false ] && [ -n "$line" ]; then
      filtered+="$line"$'\n'
    fi
  done <<< "$results"

  if [ -n "$filtered" ]; then
    echo ""
    echo "❌ BANNED TERM: '$term'"
    echo "$filtered"
    FOUND=1
  fi
done

# Special check: "Qdrant" outside of ADRs
qdrant_results=$(grep -rn \
  --include="*.md" --include="*.yml" --include="*.py" \
  --include="*.ts" --include="*.tf" --include="*.sh" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv \
  --exclude-dir=.turbo --exclude-dir=__pycache__ \
  "Qdrant" . 2>/dev/null || true)

filtered_qdrant=""
while IFS= read -r line; do
  skip=false
  for excl in "${EXCLUDE_PATTERNS[@]}"; do
    if [[ "$line" == *"$excl"* ]]; then skip=true; break; fi
  done
  [[ "$line" == *"check-stack-sync"* ]] && skip=true
  if [ "$skip" = false ] && [ -n "$line" ]; then
    filtered_qdrant+="$line"$'\n'
  fi
done <<< "$qdrant_results"

if [ -n "$filtered_qdrant" ]; then
  echo ""
  echo "❌ BANNED TERM: 'Qdrant' (use 'Supabase Vector (pgvector)' instead)"
  echo "$filtered_qdrant"
  FOUND=1
fi

# Rule 86 governance: cost_usd must only be computed in llm_service.py
# Flag any Python file outside llm_service.py that multiplies tokens * rate
token_cost_results=$(grep -rn \
  --include="*.py" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv \
  --exclude-dir=.turbo --exclude-dir=__pycache__ \
  "prompt_tokens.*\*\|completion_tokens.*\*\|total_tokens.*\*" . 2>/dev/null || true)

filtered_cost=""
while IFS= read -r line; do
  skip=false
  for excl in "${EXCLUDE_PATTERNS[@]}" "llm_service.py" "test_" "tests/"; do
    if [[ "$line" == *"$excl"* ]]; then skip=true; break; fi
  done
  if [ "$skip" = false ] && [ -n "$line" ]; then
    filtered_cost+="$line"$'\n'
  fi
done <<< "$token_cost_results"

if [ -n "$filtered_cost" ]; then
  echo ""
  echo "⚠️  Rule 86 WARNING: Token cost arithmetic found outside llm_service.py"
  echo "   Cost calculation must only happen in app/services/llm_service.py"
  echo "$filtered_cost"
  FOUND=1
fi

echo ""
if [ "$FOUND" -eq 0 ]; then
  echo "✅ Stack sync PASSED — no stale v2.4 references or governance violations found."
  exit 0
else
  echo "🚫 Stack sync FAILED — fix the above before committing."
  echo "   Intentionally preserved files (ADRs, LLD, PRD) are excluded from this check."
  exit 1
fi
