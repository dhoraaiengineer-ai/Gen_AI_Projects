"""Create all secondary indexes and GIN indexes on JSONB columns.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26 00:02:00.000000 UTC

Index strategy:
  - organization_id on EVERY table   — multi-tenant scoping (Rule 30)
  - FK columns                        — join performance
  - status columns                    — common filter predicates
  - created_at                        — time-range queries
  - GIN on JSONB columns              — ragas_metrics, payload, variant_config
  - Unique business key indexes       — already created as constraints in 0002

NOTE: CONCURRENTLY is NOT used here because Alembic runs in a transaction
and CONCURRENTLY cannot run inside a transaction block. If this migration is
applied to a live production table with millions of rows, run index creation
manually with CONCURRENTLY and mark the migration as already applied.
"""

from __future__ import annotations

from alembic import op


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── organizations ────────────────────────────────────────────────────────
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_deleted_at", "organizations", ["deleted_at"])

    # ── users ────────────────────────────────────────────────────────────────
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    # Composite: org-scoped user lookup (most common access pattern)
    op.create_index(
        "ix_users_org_email",
        "users",
        ["organization_id", "email"],
    )

    # ── pipelines ────────────────────────────────────────────────────────────
    op.create_index("ix_pipelines_organization_id", "pipelines", ["organization_id"])
    op.create_index("ix_pipelines_status", "pipelines", ["status"])
    op.create_index("ix_pipelines_deleted_at", "pipelines", ["deleted_at"])
    op.create_index("ix_pipelines_created_at", "pipelines", ["created_at"])
    # Composite: org-scoped active pipeline listing
    op.create_index(
        "ix_pipelines_org_status",
        "pipelines",
        ["organization_id", "status"],
    )

    # ── pipeline_versions ────────────────────────────────────────────────────
    op.create_index(
        "ix_pipeline_versions_pipeline_id", "pipeline_versions", ["pipeline_id"]
    )
    op.create_index(
        "ix_pipeline_versions_organization_id", "pipeline_versions", ["organization_id"]
    )
    op.create_index(
        "ix_pipeline_versions_created_at", "pipeline_versions", ["created_at"]
    )

    # ── evaluation_runs ──────────────────────────────────────────────────────
    op.create_index(
        "ix_evaluation_runs_pipeline_id", "evaluation_runs", ["pipeline_id"]
    )
    op.create_index(
        "ix_evaluation_runs_organization_id", "evaluation_runs", ["organization_id"]
    )
    op.create_index(
        "ix_evaluation_runs_run_id", "evaluation_runs", ["run_id"], unique=True
    )
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])
    op.create_index("ix_evaluation_runs_created_at", "evaluation_runs", ["created_at"])
    op.create_index(
        "ix_evaluation_runs_org_pipeline",
        "evaluation_runs",
        ["organization_id", "pipeline_id"],
    )
    # GIN index on ragas_metrics JSONB — enables fast key-path queries
    op.create_index(
        "ix_evaluation_runs_ragas_metrics_gin",
        "evaluation_runs",
        ["ragas_metrics"],
        postgresql_using="gin",
    )
    # GIN index on failure_taxonomy JSONB
    op.create_index(
        "ix_evaluation_runs_failure_taxonomy_gin",
        "evaluation_runs",
        ["failure_taxonomy"],
        postgresql_using="gin",
    )

    # ── retrieval_chunks ─────────────────────────────────────────────────────
    op.create_index(
        "ix_retrieval_chunks_pipeline_version_id",
        "retrieval_chunks",
        ["pipeline_version_id"],
    )
    op.create_index(
        "ix_retrieval_chunks_organization_id", "retrieval_chunks", ["organization_id"]
    )
    op.create_index(
        "ix_retrieval_chunks_evaluation_run_id",
        "retrieval_chunks",
        ["evaluation_run_id"],
    )
    op.create_index(
        "ix_retrieval_chunks_source_uri", "retrieval_chunks", ["source_uri"]
    )
    op.create_index(
        "ix_retrieval_chunks_chunk_strategy", "retrieval_chunks", ["chunk_strategy"]
    )
    op.create_index(
        "ix_retrieval_chunks_parent_chunk_id", "retrieval_chunks", ["parent_chunk_id"]
    )
    op.create_index(
        "ix_retrieval_chunks_created_at", "retrieval_chunks", ["created_at"]
    )

    # ── experiment_runs ──────────────────────────────────────────────────────
    op.create_index(
        "ix_experiment_runs_pipeline_id", "experiment_runs", ["pipeline_id"]
    )
    op.create_index(
        "ix_experiment_runs_organization_id", "experiment_runs", ["organization_id"]
    )
    op.create_index(
        "ix_experiment_runs_parent_evaluation_run_id",
        "experiment_runs",
        ["parent_evaluation_run_id"],
    )
    op.create_index("ix_experiment_runs_status", "experiment_runs", ["status"])
    op.create_index("ix_experiment_runs_created_at", "experiment_runs", ["created_at"])
    # GIN on variant_config — enables querying by hyperparameter values
    op.create_index(
        "ix_experiment_runs_variant_config_gin",
        "experiment_runs",
        ["variant_config"],
        postgresql_using="gin",
    )

    # ── deployments ──────────────────────────────────────────────────────────
    op.create_index("ix_deployments_pipeline_id", "deployments", ["pipeline_id"])
    op.create_index(
        "ix_deployments_organization_id", "deployments", ["organization_id"]
    )
    op.create_index(
        "ix_deployments_evaluation_run_id", "deployments", ["evaluation_run_id"]
    )
    op.create_index("ix_deployments_status", "deployments", ["status"])
    op.create_index("ix_deployments_created_at", "deployments", ["created_at"])
    op.create_index(
        "ix_deployments_org_pipeline",
        "deployments",
        ["organization_id", "pipeline_id"],
    )

    # ── audit_log ────────────────────────────────────────────────────────────
    op.create_index("ix_audit_log_organization_id", "audit_log", ["organization_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_log_run_id", "audit_log", ["run_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    # GIN on payload — enables querying audit log events by arbitrary payload keys
    op.create_index(
        "ix_audit_log_payload_gin",
        "audit_log",
        ["payload"],
        postgresql_using="gin",
    )
    # Composite: most common read pattern — org-scoped event_type filter
    op.create_index(
        "ix_audit_log_org_event_type",
        "audit_log",
        ["organization_id", "event_type"],
    )


def downgrade() -> None:
    # audit_log
    op.drop_index("ix_audit_log_org_event_type", table_name="audit_log")
    op.drop_index("ix_audit_log_payload_gin", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_run_id", table_name="audit_log")
    op.drop_index("ix_audit_log_event_type", table_name="audit_log")
    op.drop_index("ix_audit_log_organization_id", table_name="audit_log")

    # deployments
    op.drop_index("ix_deployments_org_pipeline", table_name="deployments")
    op.drop_index("ix_deployments_created_at", table_name="deployments")
    op.drop_index("ix_deployments_status", table_name="deployments")
    op.drop_index("ix_deployments_evaluation_run_id", table_name="deployments")
    op.drop_index("ix_deployments_organization_id", table_name="deployments")
    op.drop_index("ix_deployments_pipeline_id", table_name="deployments")

    # experiment_runs
    op.drop_index("ix_experiment_runs_variant_config_gin", table_name="experiment_runs")
    op.drop_index("ix_experiment_runs_created_at", table_name="experiment_runs")
    op.drop_index("ix_experiment_runs_status", table_name="experiment_runs")
    op.drop_index(
        "ix_experiment_runs_parent_evaluation_run_id", table_name="experiment_runs"
    )
    op.drop_index("ix_experiment_runs_organization_id", table_name="experiment_runs")
    op.drop_index("ix_experiment_runs_pipeline_id", table_name="experiment_runs")

    # retrieval_chunks
    op.drop_index("ix_retrieval_chunks_created_at", table_name="retrieval_chunks")
    op.drop_index("ix_retrieval_chunks_parent_chunk_id", table_name="retrieval_chunks")
    op.drop_index("ix_retrieval_chunks_chunk_strategy", table_name="retrieval_chunks")
    op.drop_index("ix_retrieval_chunks_source_uri", table_name="retrieval_chunks")
    op.drop_index(
        "ix_retrieval_chunks_evaluation_run_id", table_name="retrieval_chunks"
    )
    op.drop_index("ix_retrieval_chunks_organization_id", table_name="retrieval_chunks")
    op.drop_index(
        "ix_retrieval_chunks_pipeline_version_id", table_name="retrieval_chunks"
    )

    # evaluation_runs
    op.drop_index(
        "ix_evaluation_runs_failure_taxonomy_gin", table_name="evaluation_runs"
    )
    op.drop_index("ix_evaluation_runs_ragas_metrics_gin", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_org_pipeline", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_created_at", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_run_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_organization_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_pipeline_id", table_name="evaluation_runs")

    # pipeline_versions
    op.drop_index("ix_pipeline_versions_created_at", table_name="pipeline_versions")
    op.drop_index(
        "ix_pipeline_versions_organization_id", table_name="pipeline_versions"
    )
    op.drop_index("ix_pipeline_versions_pipeline_id", table_name="pipeline_versions")

    # pipelines
    op.drop_index("ix_pipelines_org_status", table_name="pipelines")
    op.drop_index("ix_pipelines_created_at", table_name="pipelines")
    op.drop_index("ix_pipelines_deleted_at", table_name="pipelines")
    op.drop_index("ix_pipelines_status", table_name="pipelines")
    op.drop_index("ix_pipelines_organization_id", table_name="pipelines")

    # users
    op.drop_index("ix_users_org_email", table_name="users")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_organization_id", table_name="users")

    # organizations
    op.drop_index("ix_organizations_deleted_at", table_name="organizations")
    op.drop_index("ix_organizations_slug", table_name="organizations")
