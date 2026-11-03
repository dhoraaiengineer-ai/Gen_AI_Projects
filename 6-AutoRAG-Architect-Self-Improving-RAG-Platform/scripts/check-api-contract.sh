#!/usr/bin/env bash
# check-api-contract.sh — AutoRAG v4.0 API Contract Drift Checker
#
# Regenerates autorag-client/types/generated-api.ts from the live backend's
# OpenAPI schema and diffs it against the committed version. A non-zero diff
# means a backend route/schema changed without regenerating frontend types —
# exactly the failure mode that caused the v1.0 -> v1.1 API_SPEC.md drift
# (see verification/releases/v4.0/full_api_contract_audit_11jul2026.md).
#
# Requires the backend running locally (ENVIRONMENT=local) at API_BASE_URL.
# Run manually:  bash scripts/check-api-contract.sh
# Runs via:      make sync-check
#
# Added: 11-Jul-2026 (Part E of the contract-fix pass — CLAUDE.md monorepo
# rule "OpenAPI-generated autorag-client types preferred over hand-written
# interface files" was previously unenforced; this makes it real.

set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/autorag-client" || exit 1

API_BASE_URL="${API_BASE_URL:-http://localhost:8001}"
COMMITTED="types/generated-api.ts"
TMP="$(mktemp)"

echo "AutoRAG v4.0 -- API Contract Drift Check (11-Jul-2026)"
echo "========================================================"

if ! curl -s -o /dev/null -m 5 "$API_BASE_URL/health"; then
  echo "[SKIP] Backend not reachable at $API_BASE_URL -- start it and re-run:"
  echo "       cd autorag-server && ENVIRONMENT=local uv run uvicorn app.main:app --port 8001"
  echo "       (CI: the workflow that runs this check must boot the backend service first)"
  rm -f "$TMP"
  exit 0
fi

npx --yes openapi-typescript "$API_BASE_URL/openapi.json" -o "$TMP" >/dev/null 2>&1

if [ ! -f "$COMMITTED" ]; then
  echo "[INFO] $COMMITTED does not exist yet -- generating it now."
  cp "$TMP" "$COMMITTED"
  rm -f "$TMP"
  echo "[OK] Generated. Commit it."
  exit 0
fi

if diff -q "$COMMITTED" "$TMP" >/dev/null 2>&1; then
  echo "[OK] Frontend types match the live backend schema."
  rm -f "$TMP"
  exit 0
else
  echo "[FAIL] $COMMITTED is stale -- backend routes/schemas changed."
  echo ""
  diff "$COMMITTED" "$TMP" | head -40
  echo ""
  echo "Fix: cd autorag-client && npm run generate:api-types && commit the diff."
  rm -f "$TMP"
  exit 1
fi
