"""Add documents table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-11 00:00:00.000000 UTC

Closes the gap where POST /ingest wrote files to Supabase Storage but never
persisted a row anywhere -- nothing could list, verify, or manage uploaded
documents afterward. See verification/releases/v4.0/full_api_contract_audit_11jul2026.md
Severity 1 #1.

`pipeline_id` is the FK (no separate projects table in V3 -- see
app/routes/projects.py "V3 demo bridge"). The API layer serializes
pipeline_id as project_id to satisfy API_SPEC.md v1.1 Document DTO.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
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
            nullable=False,
        ),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("storage_bucket", sa.String(255), nullable=False, server_default="documents"),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="uploaded",
            # values: uploaded | validating | chunking | embedding | indexed | failed | archived
        ),
        sa.Column(
            "embedding_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            # values: pending | processing | complete | failed
        ),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("categories", JSONB, nullable=True),
        sa.Column("doc_metadata", JSONB, nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
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
        sa.CheckConstraint(
            "status IN ('uploaded','validating','chunking','embedding','indexed','failed','archived')",
            name="ck_documents_status",
        ),
        sa.CheckConstraint(
            "embedding_status IN ('pending','processing','complete','failed')",
            name="ck_documents_embedding_status",
        ),
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_pipeline_id", "documents", ["pipeline_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])
    op.create_index("ix_documents_uploaded_at", "documents", ["uploaded_at"])
    op.create_index(
        "ix_documents_org_pipeline", "documents", ["organization_id", "pipeline_id"]
    )
    op.create_index(
        "ix_documents_tags_gin", "documents", ["tags"], postgresql_using="gin"
    )
    op.create_index(
        "ix_documents_categories_gin", "documents", ["categories"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_documents_categories_gin", table_name="documents")
    op.drop_index("ix_documents_tags_gin", table_name="documents")
    op.drop_index("ix_documents_org_pipeline", table_name="documents")
    op.drop_index("ix_documents_uploaded_at", table_name="documents")
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_pipeline_id", table_name="documents")
    op.drop_index("ix_documents_organization_id", table_name="documents")
    op.drop_table("documents")
