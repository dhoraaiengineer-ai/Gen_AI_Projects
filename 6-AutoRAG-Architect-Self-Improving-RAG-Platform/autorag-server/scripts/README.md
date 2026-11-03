# Backend Scripts

## Demo reset (`reset_demo.py` + `seed_demo.py`)

Resets local demo data to a known-good state without touching schema, users,
or the audit trail — for a clean MVP demo without rebuilding the database.

```bash
make demo-reset
```

or manually:

```bash
cd autorag-server
ENVIRONMENT=local uv run python scripts/reset_demo.py
uv run python scripts/seed_demo.py
```

**What `reset_demo.py` does:**
- Truncates the 9 runtime tables: `pipelines`, `pipeline_versions`,
  `documents`, `evaluation_runs`, `retrieval_chunks`, `experiment_runs`,
  `deployments`, `agent_metrics`, `pipeline_chunks` (Version 4.0's shared
  vector-chunk table, migration 0016).
- Drops any leftover legacy pgvector table from before Version 4.0
  (`autorag_{pipeline_id}_{version}`), discovered via an
  `information_schema` sweep.
- **Never touches**: `organizations`, `users`, `alembic_version`,
  `audit_log` (audit_log is INSERT-only compliance history — pass
  `--include-audit-log` with a typed `yes` confirmation to also clear it).
- Refuses to run unless `ENVIRONMENT=local`, or `--force` is passed —
  a hard guard against ever pointing this at staging/production.

**What `seed_demo.py` does:**
Recreates one clean "Local Demo Pipeline" by calling the real running API
(`POST /pipelines` → `POST /ingest` with the `verification/artifacts/cil-annual-report-2025.pdf`
fixture → `POST /evaluate` → poll `/jobs/{id}` to completion) — the exact
same code path a real user's browser session hits. No direct SQL inserts, no
fabricated scores. Requires `autorag-server` running locally at `:8001`.
