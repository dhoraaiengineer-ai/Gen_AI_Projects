"""Multi-tenancy (ADR-026): tenants table, tenant_id on every tenant-owned table, per-tenant
uniqueness, per-tenant kb_state, and tenant-isolation RLS policies.

Existing rows are backfilled into the demo tenant (Northwind Asset Management).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_TENANT = "0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01"

TENANT_TABLES = (
    "a2a_messages", "accounts", "agent_events", "agent_runs", "approvals", "audit_logs",
    "conversations", "customers", "document_chunks", "documents", "fraud_predictions", "holdings",
    "mcp_tool_calls", "messages", "ml_predictions", "notification_reads", "notifications",
    "orders", "portfolios", "risk_limits", "risk_scores", "trades", "transactions", "users",
)

# (table, old unique constraint, columns of the new per-tenant unique constraint)
UNIQUE_SWAPS = (
    ("accounts", "uq_accounts_account_number", ("tenant_id", "account_number")),
    ("approvals", "uq_approvals_idempotency_key", ("tenant_id", "idempotency_key")),
    ("customers", "uq_customers_customer_code", ("tenant_id", "customer_code")),
    ("documents", "uq_documents_source", ("tenant_id", "source")),
    ("portfolios", "uq_portfolios_code", ("tenant_id", "code")),
    ("transactions", "uq_transactions_transaction_ref", ("tenant_id", "transaction_ref")),
    ("risk_limits", "uq_risk_limits_portfolio_id_limit_type_scope",
     ("tenant_id", "portfolio_id", "limit_type", "scope")),
)

# Tenant from the app session setting, or from Supabase/PostgREST JWT claims.
TENANT_EXPR = (
    "COALESCE(NULLIF(current_setting('app.tenant_id', true), '')::uuid, "
    "((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb "
    "-> 'app_metadata' ->> 'tenant_id'))::uuid)"
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=42), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("plan", sa.String(length=12), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,40}$'", name=op.f("ck_tenants_slug_format")),
        sa.CheckConstraint("status IN ('active', 'suspended')", name=op.f("ck_tenants_status")),
        sa.CheckConstraint("plan IN ('demo', 'standard', 'enterprise')", name=op.f("ck_tenants_plan")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.execute(
        "INSERT INTO tenants (id, slug, name, status, plan, settings) VALUES "
        f"('{DEMO_TENANT}', 'northwind', 'Northwind Asset Management', 'active', 'demo', '{{}}')"
    )

    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.Uuid(), nullable=True))
        op.execute(f"UPDATE {table} SET tenant_id = '{DEMO_TENANT}'")  # noqa: S608 - fixed names
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"])
        op.create_foreign_key(
            op.f(f"fk_{table}_tenant_id_tenants"), table, "tenants", ["tenant_id"], ["id"],
            ondelete="CASCADE",
        )

    for table, old, columns in UNIQUE_SWAPS:
        op.drop_constraint(op.f(old), table, type_="unique")
        op.create_unique_constraint(op.f(f"uq_{table}_{'_'.join(columns)}"), table, list(columns))

    # kb_state: singleton → one row per tenant.
    op.add_column("kb_state", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.execute(f"UPDATE kb_state SET tenant_id = '{DEMO_TENANT}'")
    op.drop_constraint(op.f("ck_kb_state_singleton"), "kb_state", type_="check")
    op.drop_constraint(op.f("pk_kb_state"), "kb_state", type_="primary")
    op.drop_column("kb_state", "id")
    op.alter_column("kb_state", "tenant_id", nullable=False)
    op.create_primary_key(op.f("pk_kb_state"), "kb_state", ["tenant_id"])
    op.create_foreign_key(
        op.f("fk_kb_state_tenant_id_tenants"), "kb_state", "tenants", ["tenant_id"], ["id"],
        ondelete="CASCADE",
    )

    # RLS: new table locked down like the others; tenant isolation policy on every tenant table.
    op.execute("ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.tenants FROM anon, authenticated")
    for table in (*TENANT_TABLES, "kb_state"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON public.{table} FOR ALL "
            f"USING (tenant_id = {TENANT_EXPR}) WITH CHECK (tenant_id = {TENANT_EXPR})"
        )


def downgrade() -> None:
    for table in (*TENANT_TABLES, "kb_state"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON public.{table}")
    op.drop_constraint(op.f("fk_kb_state_tenant_id_tenants"), "kb_state", type_="foreignkey")
    op.drop_constraint(op.f("pk_kb_state"), "kb_state", type_="primary")
    op.add_column("kb_state", sa.Column("id", sa.SmallInteger(), nullable=True))
    op.execute("DELETE FROM kb_state WHERE tenant_id <> (SELECT tenant_id FROM kb_state LIMIT 1)")
    op.execute("UPDATE kb_state SET id = 1")
    op.alter_column("kb_state", "id", nullable=False)
    op.create_primary_key(op.f("pk_kb_state"), "kb_state", ["id"])
    op.create_check_constraint(op.f("ck_kb_state_singleton"), "kb_state", "id = 1")
    op.drop_column("kb_state", "tenant_id")
    for table, old, columns in UNIQUE_SWAPS:
        op.drop_constraint(op.f(f"uq_{table}_{'_'.join(columns)}"), table, type_="unique")
        op.create_unique_constraint(op.f(old), table, list(columns[1:]))
    for table in TENANT_TABLES:
        op.drop_constraint(op.f(f"fk_{table}_tenant_id_tenants"), table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        op.drop_column(table, "tenant_id")
    op.drop_table("tenants")
