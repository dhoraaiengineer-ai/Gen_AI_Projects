"""Enable row-level security on every table; make audit_logs append-only.

Supabase exposes the ``public`` schema to browser keys (roles ``anon`` and ``authenticated``) via
PostgREST. RLS with no policies denies them every row; privileges are revoked as a second layer.
The API connects as the table owner, which bypasses RLS (no FORCE), so the app is unaffected.
On plain Postgres (local Compose) the two roles are created if missing so behaviour matches.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BROWSER_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    for role in BROWSER_ROLES:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$;"
        )
    # Every table in public, including alembic_version and tables added by later migrations
    # (later migrations must call enable_rls() for their new tables).
    op.execute(
        """
        DO $$
        DECLARE t record;
        BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', t.tablename);
          END LOOP;
        END $$;
        """
    )
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.audit_logs_append_only() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs is append-only';
        END $$;
        """
    )
    op.execute(
        "CREATE TRIGGER audit_logs_no_update_delete BEFORE UPDATE OR DELETE ON public.audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION public.audit_logs_append_only()"
    )
    op.execute("REVOKE ALL ON FUNCTION public.audit_logs_append_only() FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON public.audit_logs")
    op.execute("DROP FUNCTION IF EXISTS public.audit_logs_append_only()")
    op.execute(
        """
        DO $$
        DECLARE t record;
        BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
            EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t.tablename);
          END LOOP;
        END $$;
        """
    )
