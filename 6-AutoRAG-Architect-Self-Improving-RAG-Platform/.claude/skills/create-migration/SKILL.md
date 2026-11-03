# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-migration
description: Create an Alembic database migration for schema changes

---

# Create Migration Skill

## Goal

Create a safe, production-ready Alembic migration for database schema changes.

## Steps

1. Ask for: what changed (new table, new column, index, constraint, etc.) and the target model.
2. Review the current SQLAlchemy model and existing migrations.
3. Generate the Alembic migration with both `upgrade()` and `downgrade()` functions.
4. Verify the migration:
   - UUID v7 primary keys on new tables.
   - Proper indexes on hot query paths.
   - Correct nullability and defaults.
   - Soft delete columns where appropriate.
   - Timestamps (created_at, updated_at) on new tables.
5. Check for destructive operations and flag them:
   - Column drops require data backup plan.
   - Type changes may need data migration.
   - Index creation on large tables should use `CONCURRENTLY`.
6. Summarize the migration and any risks.

## Quality rules

- Always include both upgrade and downgrade.
- Never drop columns or tables without explicit user confirmation.
- Use `op.create_index` with meaningful index names.
- Add `server_default` for new non-nullable columns on existing tables.
- Keep migration descriptions clear and specific.
- Test the migration runs without errors before marking complete.
