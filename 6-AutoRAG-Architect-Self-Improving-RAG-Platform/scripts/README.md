# 🔧 scripts — Bootstrap & Utility Scripts

**Version**: v4.0 | **Updated**: 21-Jul-2026  
**Owner**: All Teams (shared development utilities)

> This folder contains shell scripts for local development setup, infrastructure checks, and maintenance tasks.
> Scripts are OS-specific (bash for Linux/macOS, PowerShell for Windows).
> New developers should start here: [.claude/docs/setup.md](../.claude/docs/setup.md)

## 📋 Table of Contents

1. [What's in This Folder](#structure)
2. [Key Scripts](#key-scripts)
3. [Getting Started](#getting-started)
4. [Key Rules](#key-rules)
5. [Related Documentation](#related-docs)

---

## Structure

```
scripts/
│
├── dev-setup.sh             # Bash: Install uv, npm, dependencies; verify .env is present
├── dev-setup.ps1            # PowerShell: Same as above for Windows
├── check-stack-sync.sh      # Bash: Scan for stale v2.4 stack references + Rule 86 violations
├── check-stack-sync.ps1     # PowerShell: Same for Windows
├── check-api-contract.sh    # Bash: Diff generated-api.ts against the live backend's OpenAPI schema
├── check-api-contract.ps1   # PowerShell: Same for Windows
├── post_pr_update.py        # Python: post-PR auto-update (stdlib only)
├── audit_history/           # Generated: JSON snapshots from post_pr_update.py runs (gitignored)
└── LINK_REPORT.txt          # Generated: broken internal link report (gitignored)
```

## Key Scripts

| Script | Purpose | OS |
|--------|---------|-----|
| `dev-setup.sh` | Install all dependencies, verify `.env` is present, install pre-commit hooks | Linux/macOS |
| `dev-setup.ps1` | Same as above for Windows | Windows |
| `check-stack-sync.sh` | Scan for stale v2.4 stack references + Rule 86 governance violations | Linux/macOS |
| `check-stack-sync.ps1` | Same for Windows | Windows |
| `check-api-contract.sh` | Diff `generated-api.ts` against the live backend's OpenAPI schema | Linux/macOS |
| `check-api-contract.ps1` | Same for Windows | Windows |
| `post_pr_update.py` | 9-pass post-PR sync: task status, stale refs, link validation, misplaced files, HTML tracker, report, OCR/encoding fix, CHANGELOG/ROLLBACK_STRATEGY sync, deep content audit | All |

## Getting Started

**New developer (macOS/Linux):**
```bash
# Get your real .env file from your lead (Mahesh Kumar) FIRST — no template
# exists to generate one from. Place it at repo root, then copy into
# autorag-server/.env and autorag-client/.env.
bash scripts/dev-setup.sh       # Installs uv, npm, Python deps, installs pre-commit
docker compose up -d             # Start local services (Redis + backend + frontend, Cloud mode)
bash scripts/check-stack-sync.sh # Verify no stale v2.4 terms in codebase
```

**New developer (Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-setup.ps1
docker compose up -d
powershell -File scripts/check-stack-sync.ps1
```

**Existing developer — verify stack health:**
```bash
bash scripts/check-stack-sync.sh
# If services down: docker compose up -d
# If schema missing: cd autorag-server && uv run alembic upgrade head
```

**After merging a PR (lead only):**
```bash
python scripts/post_pr_update.py --dry-run   # preview all changes
python scripts/post_pr_update.py --commit    # apply + commit to development
python scripts/post_pr_update.py --pass 7   # OCR/encoding scan only
python scripts/post_pr_update.py --pass 8   # CHANGELOG.md + ROLLBACK_STRATEGY.md sync only
```

## Key Rules

- **Get your real `.env` from your lead first** — for shared work, the lead (Mahesh Kumar) distributes the real, pre-filled file directly; for individual local testing, copy the root `.env.example` instead. Place it at repo root and copy into `autorag-server/.env` and `autorag-client/.env`
- **Then run dev-setup** — installs deps and wires pre-commit hooks
- **Never commit `.env`** — blocked by `.gitignore`; no example/template files exist to accidentally commit either
- **Docker must be running** — Redis, backend, frontend, Prometheus, and Grafana run via `docker-compose.yml` (Cloud mode default — the database is Supabase Cloud, not a local container; see [docker-guide.md](../.claude/docs/docker-guide.md) for the local-database opt-in)
- **`check-stack-sync` runs in CI** — banned v2.4 terms (Presidio, GPT-4o, `pnpm`, `boto3`, `qdrant_client`, `openai` import, `trace_id` field name) will block your PR

## What `check-stack-sync` Detects

| Category | What It Catches |
|----------|----------------|
| **v2.4 stack** | `Presidio`, `GPT-4o`, `text-embedding-3-large`, `pnpm install/dev/run`, `import boto3`, `from qdrant_client`, `import openai` |
| **Field naming** | `trace_id` (must be `x_trace_id` per all GraphState fields and Rule 86) |
| **Qdrant** | Any reference outside `.claude/adr/` ADR files |
| **Rule 86** | Token cost arithmetic (`prompt_tokens * ...`) outside `llm_service.py` |
| **Trace naming** | `trace_id` field name (must be `x_trace_id` per all GraphState fields and Rule 86) |

---

## 📚 Related Documentation

| Need... | Read... | Purpose |
|---------|---------|---------|
| **Day 1 setup guide** | [../.claude/docs/setup.md](../.claude/docs/setup.md) | Complete first-day checklist for new team members |
| **Project tree reference** | [../project_docs/PROJECT_TREE.md](../project_docs/PROJECT_TREE.md) | File-by-file navigation of entire repository |
| **Make targets** | [../Makefile](../Makefile) | lint, test, format, setup, sync-check targets |
| **Docker compose** | [../docker-compose.yml](../docker-compose.yml) | PostgreSQL, Redis, Prometheus, Grafana service definitions |
| **Infra setup** | [../project_docs/ROLLBACK_STRATEGY.md](../project_docs/ROLLBACK_STRATEGY.md) | Deployment, rollback, CI/CD, Docker, troubleshooting |
| **Backend development** | [../autorag-server/README.md](../autorag-server/README.md) | FastAPI, LangGraph, local dev environment |
| **Frontend development** | [../autorag-client/README.md](../autorag-client/README.md) | Next.js dashboard setup and development |
| **Deployment** | [../infra/README.md](../infra/README.md) | Terraform provisioning, AWS deployment |
| **Governance** | [../.claude/CLAUDE.md](../.claude/CLAUDE.md) | Master contract, rules, definitions of done |
| **System overview** | [../README.md](../README.md) | Quick start, team roster, technology stack
