"""lock down Supabase Data API roles — revoke anon/authenticated, deny-by-default RLS on every table (ADR-007)

Supabase exposes the `public` schema over its REST API, and new tables were fully readable/writable by the `anon`
and `authenticated` roles (found 2026-10-26). AutoServe never uses that API: authorization lives in actor-scoped
repositories (rules/70). This migration:
  * revokes all privileges on public tables/sequences/functions from anon + authenticated (when those roles exist),
  * changes default privileges so future tables are not granted to them,
  * enables row-level security on every public table with NO policies (deny-all for non-owners).
The app connects as the table owner, which bypasses RLS, so app behaviour is unchanged. Local Docker Postgres has
no anon/authenticated roles; the revokes are skipped there, RLS is still enabled.

Revision ID: b7c1d2e3f405
Revises: 4646e056b86c
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7c1d2e3f405"
down_revision: str | None = "4646e056b86c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
DO $$
DECLARE
    r record;
    api_role text;
BEGIN
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', api_role);
        END IF;
    END LOOP;
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
    END LOOP;
END
$$;
"""

DOWNGRADE = r"""
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.tablename);
    END LOOP;
END
$$;
"""
# Downgrade intentionally does NOT re-grant anon/authenticated (re-exposing data is never an automatic step).


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
