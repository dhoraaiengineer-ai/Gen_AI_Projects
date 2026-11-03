"""Create all 9 core tables in FK dependency order.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26 00:01:00.000000 UTC

Table creation order (FK dependency chain):
  1. organizations       — root tenant, no FK deps
  2. users               — FK → organizations
  3. pipelines           — FK → organizations
  4. pipeline_versions   — FK → pipelines
  5. evaluation_runs     — FK → pipelines, organizations
  6. retrieval_chunks    — FK → pipeline_versions, evaluation_runs
  7. experiment_runs     — FK → pipelines, pipeline_versions, evaluation_runs
  8. deployments         — FK → pipelines, evaluation_runs, organizations
  9. audit_log           — no FK deps (intentional — INSERT ONLY log)

All tables:
  - UUID v7 primary key (id)
  - organization_id indexed for multi-tenant scoping
  - created_at TIMESTAMPTZ with server_default
  - deleted_at TIMESTAMPTZ nullable (soft-delete, NULL = active)
  - updated_at TIMESTAMPTZ where applicable
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. organizations ────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_organizations_name"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    # ── 2. users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default="viewer",
            # values: admin | viewer
        ),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
        sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
    )

    # ── 3. pipelines ─────────────────────────────────────────────────────────
    op.create_table(
        "pipelines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            # values: pending | running | ready | failed | decommissioned
        ),
        sa.Column(
            "chunk_strategy",
            sa.String(100),
            nullable=True,
            # values: semantic | hierarchical | late
        ),
        sa.Column(
            "embedding_model",
            sa.String(255),
            nullable=False,
            server_default="gemini-embedding-2",
        ),
        sa.Column("config_yaml", sa.Text(), nullable=True),
        sa.Column("unified_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "name", name="uq_pipelines_org_name"),
        sa.CheckConstraint(
            "status IN ('pending','running','ready','failed','decommissioned')",
            name="ck_pipelines_status",
        ),
    )

    # ── 4. pipeline_versions ─────────────────────────────────────────────────
    op.create_table(
        "pipeline_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        # Frozen vector table name — autorag_{pipeline_id}_{version_number}
        sa.Column("vector_table_name", sa.String(255), nullable=False),
        sa.Column(
            "chunk_strategy",
            sa.String(100),
            nullable=False,
            server_default="semantic",
        ),
        sa.Column("chunk_size", sa.Integer(), nullable=True),
        sa.Column("chunk_overlap", sa.Integer(), nullable=True),
        sa.Column(
            "embedding_model",
            sa.String(255),
            nullable=False,
            server_default="gemini-embedding-2",
        ),
        sa.Column("retrieval_k", sa.Integer(), nullable=True),
        sa.Column("config_snapshot", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Immutable after creation — no updated_at, no deleted_at
        sa.UniqueConstraint(
            "pipeline_id",
            "version_number",
            name="uq_pipeline_versions_pipeline_version",
        ),
        sa.UniqueConstraint(
            "vector_table_name", name="uq_pipeline_versions_vector_table"
        ),
    )

    # ── 5. evaluation_runs ───────────────────────────────────────────────────
    op.create_table(
        "evaluation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Correlation ID shared with LangGraph run
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        # Unified Score components
        sa.Column("unified_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("recall", sa.Numeric(4, 3), nullable=True),
        sa.Column("quality", sa.Numeric(4, 3), nullable=True),
        sa.Column("faithfulness", sa.Numeric(4, 3), nullable=True),
        sa.Column("latency_p95_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        # RAGAS + Adversarial
        sa.Column(
            "adversarial_passed", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("ragas_metrics", JSONB, nullable=True),
        sa.Column("failure_taxonomy", JSONB, nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            # values: pending | running | completed | blocked
        ),
        sa.Column("dataset_version", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("run_id", name="uq_evaluation_runs_run_id"),
        sa.CheckConstraint(
            "faithfulness IS NULL OR faithfulness >= 0",
            name="ck_evaluation_runs_faithfulness_nonneg",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','blocked')",
            name="ck_evaluation_runs_status",
        ),
    )

    # ── 6. retrieval_chunks ──────────────────────────────────────────────────
    op.create_table(
        "retrieval_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "pipeline_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipeline_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Mandatory metadata — Rule 50
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("chunk_strategy", sa.String(100), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        # Hierarchical chunking — parent reference
        sa.Column(
            "parent_chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("retrieval_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ── 7. experiment_runs ───────────────────────────────────────────────────
    op.create_table(
        "experiment_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_evaluation_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "result_pipeline_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipeline_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # MLflow cross-reference
        sa.Column("mlflow_run_id", sa.String(255), nullable=True),
        sa.Column("variant_config", JSONB, nullable=False),
        sa.Column("unified_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("score_delta", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            # values: pending | running | completed | failed
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_experiment_runs_status",
        ),
    )

    # ── 8. deployments ───────────────────────────────────────────────────────
    op.create_table(
        "deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ECS task ARN — MUST be immutable SHA tag (e.g. sha256:abc123)
        sa.Column("task_arn", sa.String(500), nullable=False),
        # Previous Blue task ARN for instant rollback
        sa.Column("rollback_task_arn", sa.String(500), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            # values: pending | blue_green | promoted | rolled_back | failed
        ),
        # Snapshot — non-mutable after creation
        sa.Column("unified_score_at_deploy", sa.Numeric(4, 3), nullable=True),
        # Blue/Green canary timestamps
        sa.Column("deployed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("promoted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','blue_green','promoted','rolled_back','failed')",
            name="ck_deployments_status",
        ),
    )

    # ── 9. audit_log ─────────────────────────────────────────────────────────
    # INSERT ONLY — DB trigger enforced in migration 0004
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=True),
        # No updated_at — INSERT ONLY, rows are immutable
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'pipeline_created','pipeline_updated','ingest_started','ingest_completed',"
            "'eval_started','eval_completed','deploy_started','deploy_completed',"
            "'rollback_triggered','hitl_approved','hitl_rejected'"
            ")",
            name="ck_audit_log_event_type",
        ),
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("audit_log")
    op.drop_table("deployments")
    op.drop_table("experiment_runs")
    op.drop_table("retrieval_chunks")
    op.drop_table("evaluation_runs")
    op.drop_table("pipeline_versions")
    op.drop_table("pipelines")
    op.drop_table("users")
    op.drop_table("organizations")
