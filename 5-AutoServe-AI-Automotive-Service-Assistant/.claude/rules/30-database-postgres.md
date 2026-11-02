# 30 — Database (PostgreSQL 16 + pgvector)

**Purpose:** Correct, auditable, isolated data.

## MUST
- Every schema change is an Alembic migration: autogenerate, then review by hand. Make migrations reversible where possible.
- UUID PKs (`gen_random_uuid()`), `created_at`/`updated_at` timestamptz. Soft delete (`deleted_at`) only where `specs/database.md` says so.
- Foreign keys, plus indexes on every FK and filter column (`dealer_id`, `owner_id`, `vin`, `status`).
- `NUMERIC(12,2)` for money, `NUMERIC(6,2)` for hours. Never float.
- Human-readable references from DB sequences: `RO-{YYYY}-{6 digits}`, `WC-{YYYY}-{6 digits}`.
- `audit_log` is INSERT-only. `hash = sha256(prev_hash || canonical_json(payload))`. A trigger rejects UPDATE/DELETE.
- Status changes write `ro_status_history` / `warranty_status_history` **in the same transaction** as the status update.
- pgvector: one fixed embedding dimension per deployment (ADR-003); HNSW index with `vector_cosine_ops`; GIN index on the `tsvector` column for FTS.
- Mark PII columns in `specs/database.md`. Retention follows `RETENTION_DAYS_*`.

## MUST NOT
- Build SQL with string formatting. Use SQLAlchemy expressions or bound parameters.
- Grant the app DB role UPDATE/DELETE on `audit_log`.
- Query RO/vehicle/claim tables outside a repository that applies the actor filter.
- Store payment card or bank data (out of scope).

## Good
```sql
CREATE TRIGGER audit_log_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION raise_immutable();
```

## Bad
```python
# bypasses transition(), writes no history, SQL injection
await session.execute(text(f"UPDATE repair_orders SET status='{new}' WHERE id='{ro_id}'"))
```
