"""Evaluation Center -- golden datasets, versions, questions, configs, batch runs.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-24 00:00:00.000000 UTC

Closes a real gap: `evaluation_runs` (migration 0002) only ever represents a
single query dispatched against a single pipeline -- there is no way to
define a reusable, versioned set of "golden questions" and run all of them
against a pipeline as one batch, and no persisted, reusable evaluation
configuration (retriever/reranker/embedding/judge settings were only ever
passed ad-hoc per single-question request). This migration adds that,
following the same immutability pattern `pipeline_versions` (migration 0002)
and `pipeline_chunks` (migration 0016) already established for this schema:
new versions are created explicitly and never mutated in place.

Six tables, in FK dependency order:
  1. evaluation_datasets         -- mutable container (name/description/domain)
  2. evaluation_dataset_versions -- immutable version snapshots (lifecycle_status)
  3. golden_questions            -- individual benchmark questions, FK'd to a version
  4. evaluation_configs          -- persisted, reusable, immutable batch-run config
  5. batch_runs                  -- header row for one "run N questions" execution
  6. batch_evaluations           -- per-question ledger within a batch_run, FK'd to
                                     evaluation_runs once that question's real graph
                                     run completes; carries the human-review workflow

Design notes:
  - `golden_questions.dataset_version_id` FKs to the version, not the dataset,
    so editing a question via "publish new version" never silently rewrites
    a past benchmark's results (see evaluation_dataset_repository.py's
    publish_new_version).
  - `evaluation_dataset_versions.lifecycle_status` gates which versions are
    selectable for a batch run -- only 'published' (enforced in
    batch_eval_service.start_batch_run, not at the DB layer, since it's a
    business rule that needs a clear 422, not a CHECK constraint failure).
  - `evaluation_configs` rows are never updated after creation -- an "edit"
    creates a new row, so `batch_runs.config_id` always points to the exact
    config that was actually used, keeping historical runs reproducible.
  - `golden_questions.review_status` (draft/under_review/approved/rejected/
    archived) is a per-question editorial workflow, independent of
    `batch_evaluations.review_status` (unreviewed/approved/rejected/
    corrected), which reviews a batch run's per-question *result*, not the
    golden question itself.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. evaluation_datasets ──────────────────────────────────────────────
    op.create_table(
        "evaluation_datasets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("tags", JSONB, nullable=True),  # e.g. ["finance", "annual-report"]
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="active",
            # values: active | archived
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "name", name="uq_evaluation_datasets_org_name"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_evaluation_datasets_status"),
    )
    op.create_index(
        "ix_evaluation_datasets_organization_id", "evaluation_datasets", ["organization_id"]
    )

    # ── 2. evaluation_dataset_versions ──────────────────────────────────────
    op.create_table(
        "evaluation_dataset_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "dataset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(50), nullable=False),  # e.g. "v1", "v2"
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(50),
            nullable=False,
            server_default="draft",
            # values: draft | under_review | published | archived
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "dataset_id", "version_label", name="uq_evaluation_dataset_versions_dataset_label"
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('draft','under_review','published','archived')",
            name="ck_evaluation_dataset_versions_lifecycle_status",
        ),
    )
    op.create_index(
        "ix_evaluation_dataset_versions_dataset_id",
        "evaluation_dataset_versions",
        ["dataset_id"],
    )
    op.create_index(
        "ix_evaluation_dataset_versions_organization_id",
        "evaluation_dataset_versions",
        ["organization_id"],
    )
    op.create_index(
        "ix_evaluation_dataset_versions_lifecycle_status",
        "evaluation_dataset_versions",
        ["lifecycle_status"],
    )

    # ── 3. golden_questions ─────────────────────────────────────────────────
    op.create_table(
        "golden_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "dataset_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=True),
        sa.Column("expected_context", sa.Text(), nullable=True),
        sa.Column(
            "reference_document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reference_pages", sa.String(100), nullable=True),  # e.g. "45-46"
        sa.Column("relevant_chunk_ids", JSONB, nullable=True),  # e.g. ["chunk_421", "chunk_422"]
        sa.Column("category", sa.String(100), nullable=True),  # e.g. "Finance", "Legal"
        sa.Column(
            "difficulty",
            sa.String(20),
            nullable=True,
            # values: easy | medium | hard | expert
        ),
        sa.Column(
            "metric_focus",
            sa.String(50),
            nullable=True,
            # e.g. faithfulness | context_recall | answer_correctness | retrieval
        ),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column(
            "review_status",
            sa.String(50),
            nullable=False,
            server_default="draft",
            # values: draft | under_review | approved | rejected | archived
        ),
        sa.Column(
            "reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            "difficulty IS NULL OR difficulty IN ('easy','medium','hard','expert')",
            name="ck_golden_questions_difficulty",
        ),
        sa.CheckConstraint(
            "review_status IN ('draft','under_review','approved','rejected','archived')",
            name="ck_golden_questions_review_status",
        ),
    )
    op.create_index(
        "ix_golden_questions_dataset_version_id", "golden_questions", ["dataset_version_id"]
    )
    op.create_index("ix_golden_questions_organization_id", "golden_questions", ["organization_id"])
    op.create_index("ix_golden_questions_review_status", "golden_questions", ["review_status"])
    op.create_index("ix_golden_questions_category", "golden_questions", ["category"])

    # ── 4. evaluation_configs ───────────────────────────────────────────────
    op.create_table(
        "evaluation_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("retriever_strategy", sa.String(100), nullable=True),
        sa.Column("reranker", sa.String(100), nullable=True),
        sa.Column("embedding_model", sa.String(255), nullable=True),
        sa.Column("top_k", sa.Integer(), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=True),
        sa.Column("judge_provider", sa.String(100), nullable=True),
        sa.Column("judge_model", sa.String(255), nullable=True),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_evaluation_configs_organization_id", "evaluation_configs", ["organization_id"]
    )
    op.create_index("ix_evaluation_configs_pipeline_id", "evaluation_configs", ["pipeline_id"])

    # ── 5. batch_runs ────────────────────────────────────────────────────────
    op.create_table(
        "batch_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="queued",
            # values: queued | running | completed | cancelled | failed
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','cancelled','failed')",
            name="ck_batch_runs_status",
        ),
    )
    op.create_index("ix_batch_runs_organization_id", "batch_runs", ["organization_id"])
    op.create_index("ix_batch_runs_dataset_version_id", "batch_runs", ["dataset_version_id"])
    op.create_index("ix_batch_runs_pipeline_id", "batch_runs", ["pipeline_id"])
    op.create_index("ix_batch_runs_status", "batch_runs", ["status"])

    # ── 6. batch_evaluations ────────────────────────────────────────────────
    op.create_table(
        "batch_evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "batch_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("batch_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "golden_question_id",
            UUID(as_uuid=True),
            sa.ForeignKey("golden_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "evaluation_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            # values: pending | running | completed | failed
        ),
        sa.Column(
            "review_status",
            sa.String(50),
            nullable=False,
            server_default="unreviewed",
            # values: unreviewed | approved | rejected | corrected
        ),
        sa.Column(
            "reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("corrected_answer", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "batch_run_id", "golden_question_id", name="uq_batch_evaluations_run_question"
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_batch_evaluations_status",
        ),
        sa.CheckConstraint(
            "review_status IN ('unreviewed','approved','rejected','corrected')",
            name="ck_batch_evaluations_review_status",
        ),
    )
    op.create_index("ix_batch_evaluations_batch_run_id", "batch_evaluations", ["batch_run_id"])
    op.create_index(
        "ix_batch_evaluations_organization_id", "batch_evaluations", ["organization_id"]
    )
    op.create_index(
        "ix_batch_evaluations_golden_question_id", "batch_evaluations", ["golden_question_id"]
    )
    op.create_index("ix_batch_evaluations_status", "batch_evaluations", ["status"])
    op.create_index(
        "ix_batch_evaluations_review_status", "batch_evaluations", ["review_status"]
    )


def downgrade() -> None:
    op.drop_table("batch_evaluations")
    op.drop_table("batch_runs")
    op.drop_table("evaluation_configs")
    op.drop_table("golden_questions")
    op.drop_table("evaluation_dataset_versions")
    op.drop_table("evaluation_datasets")
