---
name: create-migration
description: Checklist for writing an AutoServe AI Alembic migration (tables, indexes, sequences, pgvector, audit triggers) safely and reversibly.
---

# Create a database migration

Read first: `.claude/rules/30-database-postgres.md`, `.claude/specs/database.md`.

## Checklist
1. [ ] Update `specs/database.md` (and `docs/DB_SCHEMA.md`) first: columns, PII marking, relationships.
2. [ ] Update the SQLAlchemy model in `autoserve-server/app/models/`.
3. [ ] `cd autoserve-server && uv run alembic revision --autogenerate -m "<verb>_<object>"`, then **review the generated file by hand**.
4. [ ] Hand-add what autogenerate misses: `CREATE EXTENSION IF NOT EXISTS vector`, sequences, functions, triggers, HNSW/GIN indexes, CHECK constraints for enums/status.
5. [ ] Money `NUMERIC(12,2)`, hours `NUMERIC(6,2)`; FKs indexed; `dealer_id`/`owner_id`/`status` indexed.
6. [ ] Write `downgrade()` (or document why it is irreversible).
7. [ ] Audit-related: the app role keeps INSERT/SELECT only on `audit_log`; the trigger blocks UPDATE/DELETE.
8. [ ] Test on a clean DB: `make migrate`, then `alembic downgrade -1 && alembic upgrade head`.
9. [ ] Run integration tests against real Postgres; paste output.
10. [ ] Note data backfill or re-ingest steps (e.g. embedding dimension change) in the PR and runbook.
