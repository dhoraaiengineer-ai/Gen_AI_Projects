---
name: add-migration
description: Create and apply an Alembic migration against Supabase Postgres safely (session pooler, constraints, indexes, downgrade). Use when changing app/db/models.py.
---

# Add a migration

1. Change the SQLAlchemy models in `app/db/models.py`. Every table needs:
   - a primary key
   - foreign keys with explicit `ondelete`
   - `CHECK` constraints for quantities and prices (`>= 0`)
   - `created_at` and `updated_at` as `timestamptz`, with server defaults
   - indexes on lookup columns
2. Generate the migration with `uv run alembic revision --autogenerate -m "<what>"`, then **review the file**.
   Autogenerate misses `CREATE EXTENSION vector`, GIN or HNSW indexes and generated `tsvector` columns, so add
   those by hand.
3. Make sure `downgrade()` reverses everything.
4. Apply it with `uv run alembic upgrade head`. This uses `DATABASE_MIGRATION_URL`, the session pooler on port
   5432. **Never use the transaction pooler (6543) for DDL.**
5. Tell the user before applying it to Supabase. This is a write to their database.
6. Run the repository tests: `RUN_INTEGRATION=1 uv run pytest -m integration tests/integration`.
