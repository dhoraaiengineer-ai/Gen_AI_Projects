# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 30: AutoRAG Database

## Enforces:

1.  **Engine**: Supabase PostgreSQL (managed — no self-hosted RDS).
2.  **Primary Keys**: Mandatory **UUID v7** (time-sortable GUIDs).
3.  **Audit Logs**: Strictly **INSERT-ONLY** `audit_log` table with 14 approved event types.
4.  **Migrations**: Alembic for all schema changes; must include `upgrade` and `downgrade`.
5.  **Tenancy**: All tables must include an `organization_id` index.

## Anti-Patterns:

- Serial integer primary keys.
- Deleting or updating records in the `audit_log`.
- Running schema changes without an Alembic migration.
