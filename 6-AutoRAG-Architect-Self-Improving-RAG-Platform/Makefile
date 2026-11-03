# AutoRAG Architect v4.0 — Developer Makefile
# Status: Aligned with frozen contracts (DB_SCHEMA v1.0, GRAPH_STATE v1.0, API_SPEC v1.2)
# Usage: make <target>
# Requires: uv (Python), node/npm (TypeScript)
# Install uv: https://docs.astral.sh/uv/getting-started/installation/

.PHONY: help setup lint format typecheck test clean sync-check verify-contracts dev security check-kits post-merge audit-mechanical audit-semantic demo-reset

help:
	@echo "AutoRAG Architect v4.0 - Available Targets"
	@echo ""
	@echo "Setup & Verification:"
	@echo "  make setup           Install Python deps (uv), Node deps (npm), pre-commit hooks"
	@echo "  make verify-contracts Check frozen contracts (DB_SCHEMA, GRAPH_STATE, API_SPEC)"
	@echo "  make sync-check      Scan for stale v2.4 stack refs (blocks on failure)"
	@echo "  make security        Run bandit SAST + gitleaks secret scan locally"
	@echo ""
	@echo "Development:"
	@echo "  make dev             Full workflow: lint → typecheck → test"
	@echo "  make lint            Run ruff + mypy (autorag-server) and ESLint (autorag-client)"
	@echo "  make format          Auto-fix formatting: ruff (autorag-server) + prettier (autorag-client)"
	@echo "  make typecheck       Run mypy (autorag-server) and tsc --noEmit (autorag-client)"
	@echo "  make test            Run pytest (autorag-server)"
	@echo ""
	@echo "Demo:"
	@echo "  make demo-reset      Truncate runtime data + reseed one clean demo pipeline (local only)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean           Remove __pycache__, .mypy_cache, .ruff_cache"
	@echo "  make check-kits      Scan starter kits for OCR corruption (f→e pattern)"
	@echo ""
	@echo "Post-PR Housekeeping (run after every PR merge):"
	@echo "  make post-merge      Step 1 (mechanical) + Step 2 (semantic audit) in sequence"
	@echo "  make audit-mechanical  Step 1 only: dates, paths, versions, HTML tracker, OCR, changelog/rollback"
	@echo "  make audit-semantic    Step 2 only: deep Claude audit of entire project"

# ── Setup (one-time, run after cloning) ──────────────────────────────────────
setup:
	@echo "==> Installing Python dev dependencies (uv)"
	cd autorag-server && uv sync --all-groups
	@echo "==> Installing pre-commit hooks"
	cd autorag-server && uv run pre-commit install
	@echo "==> Installing Node dependencies (npm workspaces)"
	npm install
	@echo "==> Setup complete. Run: make verify-contracts && make dev"

# ── Frozen Contract Verification ──────────────────────────────────────────────
verify-contracts:
	@echo "==> Verifying frozen contracts (v3.0)"
	@echo "    Checking: DB_SCHEMA.md v1.0, GRAPH_STATE.md v1.0, API_SPEC.md v1.2"
	@if grep -q "vector(768)" .claude/docs/DB_SCHEMA.md && \
	     grep -q "vector(768)" .claude/docs/GRAPH_STATE.md && \
	     grep -q "/api/v1/deploy/rollback" .claude/docs/API_SPEC.md && \
	     grep -q "GET /health" .claude/docs/API_SPEC.md && \
	     grep -q "GET /api/v1/health" .claude/docs/API_SPEC.md; then \
	  echo "✅ All frozen contracts verified"; \
	else \
	  echo "❌ Contract mismatch detected"; \
	  echo "   Check: Embedding dims (768), API endpoints (/api/v1/deploy/rollback), Health checks"; \
	  exit 1; \
	fi

# ── Development Workflow ─────────────────────────────────────────────────────
dev: verify-contracts lint typecheck test
	@echo "✅ All checks passed (lint → typecheck → test)"

# ── Lint ─────────────────────────────────────────────────────────────────────
lint: lint-autorag-server lint-autorag-client

lint-autorag-server:
	@echo "==> ruff check (autorag-server)"
	cd autorag-server && uv run ruff check app
	@echo "==> mypy (autorag-server)"
	cd autorag-server && uv run mypy app --ignore-missing-imports --config-file pyproject.toml

lint-autorag-client:
	@echo "==> ESLint (autorag-client)"
	npm run lint --workspace=autorag-client

# ── Format ───────────────────────────────────────────────────────────────────
format: format-autorag-server format-autorag-client

format-autorag-server:
	@echo "==> ruff format + fix (autorag-server)"
	cd autorag-server && uv run ruff format .
	cd autorag-server && uv run ruff check --fix .

format-autorag-client:
	@echo "==> prettier (autorag-client)"
	npm run format --workspace=autorag-client

# ── Type Check ───────────────────────────────────────────────────────────────
typecheck: typecheck-autorag-server typecheck-autorag-client

typecheck-autorag-server:
	cd autorag-server && uv run mypy app --ignore-missing-imports --config-file pyproject.toml

typecheck-autorag-client:
	npm run typecheck --workspace=autorag-client

# ── Test ─────────────────────────────────────────────────────────────────────
test:
	cd autorag-server && uv run pytest -q

# ── Demo Reset ───────────────────────────────────────────────────────────────
# Truncates runtime tables (pipelines, documents, evaluation runs, etc.) and
# reseeds one clean demo pipeline through the real running API. Preserves
# users, organizations, audit_log, and schema. See autorag-server/scripts/README.md.
# Requires: autorag-server running locally at :8000 (for the seed step).
demo-reset:
	@echo "==> Resetting demo data (local only)"
	cd autorag-server && ENVIRONMENT=local uv run python scripts/reset_demo.py
	@echo "==> Seeding clean demo pipeline via live API"
	cd autorag-server && uv run python scripts/seed_demo.py

# ── Security Scan (local mirror of CI security.yml) ──────────────────────────
security:
	@echo "==> bandit SAST scan (autorag-server)"
	cd autorag-server && uv run bandit -r app -c ../security/bandit.yaml -q
	@echo "==> gitleaks secret scan"
	gitleaks detect --config security/.gitleaks.toml --source . --no-banner

# ── Stack Sync Check ─────────────────────────────────────────────────────────
sync-check:
	@echo "==> Stack drift check (banned v2.4 terms)"
	@bash scripts/check-stack-sync.sh
	@echo "==> API contract drift check (frontend types vs live backend OpenAPI schema)"
	@bash scripts/check-api-contract.sh
	@echo "==> Alert/metric consistency check (autorag-alerts.yml vs app/metrics.py)"
	@cd autorag-server && uv run python ../scripts/check-alert-metrics.py

# ── Starter Kit OCR Corruption Check ────────────────────────────────────────
# Detects the known f→e OCR corruption pattern from original PDF extraction.
# Run: make check-kits  (fails if any corrupted terms found in project-guides/)
# NOTE: project-guides/ was removed 17-Jul-2026 (project complete, starter kits
# no longer needed). This target now scans a nonexistent directory and will
# always report "clean" trivially -- kept for now in case starter kits return
# for a future phase, but treat its output as a no-op, not a real check.
check-kits:
	@echo "==> Scanning starter kits for OCR corruption (f→e pattern)"
	@FOUND=0; \
	for term in ruee eeat erom erozen eailed eound beeore notieied Notiey Coneirm eaitheulness eield eirst eiles notieication saeety preeix eneorced verieied; do \
	  MATCHES=$$(grep -rl "$$term" project-guides/ 2>/dev/null | grep "STARTER_KIT.md" | wc -l | tr -d ' '); \
	  if [ "$$MATCHES" -gt "0" ]; then \
	    echo "❌ OCR corruption '$$term' found in:"; \
	    grep -rl "$$term" project-guides/ 2>/dev/null | grep "STARTER_KIT.md"; \
	    FOUND=1; \
	  fi; \
	done; \
	if [ "$$FOUND" -eq "0" ]; then echo "✅ No OCR corruption found in starter kits"; fi; \
	exit $$FOUND

# ── Post-PR Housekeeping ──────────────────────────────────────────────────────
# Run after every PR merge to development.
# Step 1 (mechanical): fixes dates, paths, versions, HTML tracker, OCR encoding, CHANGELOG/ROLLBACK_STRATEGY sync.
# Step 2 (semantic):   deep Claude audit — reads every file, fixes stale content.
#
# Requires: claude CLI installed and authenticated (claude --version to verify)
#   Install: https://claude.ai/code
# Note: audit-semantic runs claude -p in interactive approval mode.
#   Claude describes each file edit and waits for your approval before writing.
#   You stay in control of every change.
#
# Usage:
#   make post-merge           # both steps in sequence
#   make audit-mechanical     # Step 1 only (fast, ~10s, no claude needed)
#   make audit-semantic       # Step 2 only (slower, requires claude CLI)

audit-mechanical:
	@echo "==> Step 1: Mechanical fixes (dates, paths, versions, HTML tracker, OCR, changelog/rollback)"
	python scripts/post_pr_update.py --commit --history
	@echo "✅ Step 1 complete"

audit-semantic:
	@echo "==> Step 2: Semantic audit (Claude reads every file, fixes stale content)"
	@if ! command -v claude >/dev/null 2>&1; then \
	  echo "❌ claude CLI not found. Install from https://claude.ai/code then re-run."; \
	  exit 1; \
	fi
	claude -p "Deep audit the entire project -- every file, every subfolder. Fix stale refs, wrong versions, wrong LLM names, wrong task IDs, broken markdown links, outdated paths. Push to development when done."
	@echo "✅ Step 2 complete"

post-merge: audit-mechanical audit-semantic
	@echo ""
	@echo "✅ Post-merge housekeeping complete (mechanical + semantic)."

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
