"""Unit tests for the D-3 SQLAlchemy ORM models.

These tests are intentionally DB-free — they assert the *shape* of the ORM
metadata (tables, columns, constraints, indexes, defaults) against the
frozen schema. The live-DB behaviours (audit_log UPDATE/DELETE trigger,
autogenerate == empty) are covered by integration tests / CI against the
dev Supabase instance.

Rule 30: UUID v7 PKs, organization_id indexed on every tenant-scoped table,
soft-delete on mutable tables, audit_log INSERT-ONLY.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import configure_mappers

from app.db.base import Base as DbBase
from app.models import (
    APPROVED_EVENT_TYPES,
    AuditLog,
    Base,
    BatchEvaluation,
    BatchRun,
    Deployment,
    Document,
    EvaluationConfig,
    EvaluationDataset,
    EvaluationDatasetVersion,
    EvaluationRun,
    ExperimentRun,
    GoldenQuestion,
    Organization,
    Pipeline,
    PipelineVersion,
    RetrievalChunk,
    User,
    uuid7,
)

ALL_MODELS = [
    Organization,
    User,
    Pipeline,
    PipelineVersion,
    Document,
    EvaluationRun,
    RetrievalChunk,
    ExperimentRun,
    Deployment,
    AuditLog,
    EvaluationDataset,
    EvaluationDatasetVersion,
    GoldenQuestion,
    EvaluationConfig,
    BatchRun,
    BatchEvaluation,
]

# 16 tables (was 10 -- migration 0017, 24-Jul-2026, added the Evaluation
# Center's 6 golden-dataset/batch-evaluation tables; test updated to match.
# agent_metrics (ADR-006) and pipeline_chunks (migration 0016) are real
# tables too but aren't ORM-mapped through app.models, so they're out of
# scope here.
EXPECTED_TABLES = {
    "organizations",
    "users",
    "pipelines",
    "pipeline_versions",
    "documents",
    "evaluation_runs",
    "retrieval_chunks",
    "experiment_runs",
    "deployments",
    "audit_log",
    "evaluation_datasets",
    "evaluation_dataset_versions",
    "golden_questions",
    "evaluation_configs",
    "batch_runs",
    "batch_evaluations",
}

# Tenant-scoped tables carry organization_id (organizations IS the tenant root).
ORG_SCOPED_MODELS = [m for m in ALL_MODELS if m is not Organization]

# Only mutable business entities are soft-deletable; append-only / immutable
# tables (versions, runs, chunks, experiments, deployments, audit_log,
# dataset versions, golden questions, configs, batch runs/evaluations) are
# not -- EvaluationDataset itself IS soft-deletable (same mutable-container
# pattern as Pipeline/Document).
SOFT_DELETE_MODELS = [Organization, User, Pipeline, Document, EvaluationDataset]


# ── Base / metadata unification ──────────────────────────────────────────────


def test_single_canonical_base() -> None:
    """app.db.base.Base must be the SAME object as app.models.base.Base.

    Two DeclarativeBase instances = two MetaData registries = Alembic
    autogenerate sees only half the tables. This guards against regressing
    the split-brain that D-3 fixed.
    """
    assert Base is DbBase


def test_all_ten_tables_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_mappers_configure_cleanly() -> None:
    """All relationships resolve — catches broken back_populates wiring."""
    configure_mappers()


# ── UUID v7 (Rule 30) ────────────────────────────────────────────────────────


def test_uuid7_is_version_7() -> None:
    value = uuid7()
    assert isinstance(value, uuid.UUID)
    assert value.version == 7


def test_uuid7_is_unique() -> None:
    assert uuid7() != uuid7()


def test_all_primary_keys_default_to_uuid7() -> None:
    for model in ALL_MODELS:
        pk = model.__table__.c.id
        assert pk.primary_key, f"{model.__name__}.id is not a primary key"
        assert pk.default is not None, f"{model.__name__}.id has no default"
        assert pk.default.is_callable, f"{model.__name__}.id default is not callable"
        # SQLAlchemy wraps a 0-arg callable default as ``lambda ctx: uuid7()``,
        # so we invoke it (ctx ignored) and confirm it yields a UUID v7.
        generated = pk.default.arg(None)
        assert isinstance(generated, uuid.UUID), (
            f"{model.__name__}.id default did not return a UUID"
        )
        assert generated.version == 7, f"{model.__name__}.id default is not UUID v7"


# ── Multi-tenancy (Rule 30) ──────────────────────────────────────────────────


def test_org_scoped_models_have_organization_id() -> None:
    for model in ORG_SCOPED_MODELS:
        assert "organization_id" in model.__table__.c, (
            f"{model.__name__} missing organization_id"
        )


def test_organization_id_is_indexed_on_every_scoped_table() -> None:
    for model in ORG_SCOPED_MODELS:
        indexed_cols = {col.name for idx in model.__table__.indexes for col in idx.columns}
        assert "organization_id" in indexed_cols, (
            f"{model.__name__}.organization_id is not indexed"
        )


def test_organization_id_nullability() -> None:
    # audit_log is a system log — org may be unknown; everywhere else it's required.
    assert AuditLog.__table__.c.organization_id.nullable is True
    for model in [m for m in ORG_SCOPED_MODELS if m is not AuditLog]:
        assert model.__table__.c.organization_id.nullable is False, (
            f"{model.__name__}.organization_id should be NOT NULL"
        )


# ── Soft-delete ──────────────────────────────────────────────────────────────


def test_soft_delete_columns() -> None:
    for model in SOFT_DELETE_MODELS:
        assert "deleted_at" in model.__table__.c, (
            f"{model.__name__} should have deleted_at (soft-delete)"
        )
    for model in [m for m in ALL_MODELS if m not in SOFT_DELETE_MODELS]:
        assert "deleted_at" not in model.__table__.c, (
            f"{model.__name__} should be append-only (no deleted_at)"
        )


# ── audit_log INSERT-ONLY contract (Rule 86 — 14 event types) ────────────────


def test_audit_log_has_fourteen_event_types() -> None:
    """pii_redacted added 13-Jul-2026, migration 0011 (P0.7-2)."""
    assert len(APPROVED_EVENT_TYPES) == 14
    assert "cost_limit_exceeded" in APPROVED_EVENT_TYPES
    assert "guardrail_blocked" in APPROVED_EVENT_TYPES
    assert "pii_redacted" in APPROVED_EVENT_TYPES


def test_audit_log_event_type_check_constraint_present() -> None:
    names = {c.name for c in AuditLog.__table__.constraints}
    assert "ck_audit_log_event_type" in names


def test_audit_log_has_no_mutation_methods() -> None:
    # INSERT-ONLY at the ORM layer: no update()/delete() helpers exposed.
    assert not hasattr(AuditLog, "update")
    assert not hasattr(AuditLog, "delete")


# ── retrieval_chunks drift regression guard (D-3 reconcile) ──────────────────


def test_retrieval_chunk_matches_migration_columns() -> None:
    cols = set(RetrievalChunk.__table__.c.keys())
    # Phantom columns removed during reconcile — must stay gone.
    assert "source_doc_id" not in cols
    assert "text_preview" not in cols
    # Migration columns that were missing — must be present.
    assert "evaluation_run_id" in cols
    assert "content_hash" in cols


# ── Frozen embedding contract surfaced via the default ───────────────────────


def test_embedding_model_defaults_to_gemini() -> None:
    default = Pipeline.__table__.c.embedding_model.server_default
    assert default is not None
    # A plain-string server_default is stored as a raw str on ``.arg``.
    assert "gemini-embedding-2" in str(default.arg)


# ── Construction works without a DB session ──────────────────────────────────


def test_models_instantiate_in_memory() -> None:
    org_id = uuid7()
    pipeline = Pipeline(organization_id=org_id, name="demo")
    assert pipeline.organization_id == org_id
    assert pipeline.name == "demo"
    # id/created_at are populated by the DB on INSERT, not at construction.
    assert pipeline.id is None
