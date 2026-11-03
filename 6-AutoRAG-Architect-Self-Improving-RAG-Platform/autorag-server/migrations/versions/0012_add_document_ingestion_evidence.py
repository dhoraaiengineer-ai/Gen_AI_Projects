"""Add page_count/char_count/pii_redaction_count/pii_counts_by_type to documents.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-13 00:00:00.000000 UTC

P0.7 follow-up (13-Jul-2026): page count, character count, and PII redaction
counts are document-level facts that must be persisted once, at ingestion
time, by the node that actually parses/masks the document -- not
reconstructed later from a run's node_trace (which is per-run evidence, not
per-document evidence; a document can be referenced by multiple runs).

page_count/char_count are nullable (no server_default) because 0 would be
indistinguishable from "measured and genuinely empty" -- NULL means "not
yet measured for this document" (e.g. rows created before this migration,
or a document whose ingestion_node pass hasn't run yet). pii_redaction_count
defaults to 0 (a real, valid "zero PII found" measurement, not a sentinel).
pii_counts_by_type is nullable JSONB (canonical PII types from
app/services/pii_engine.py -- P0.7-1), e.g. {"EMAIL": 8, "SSN": 0}.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_TABLE = "documents"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column(_TABLE, sa.Column("char_count", sa.Integer(), nullable=True))
    op.add_column(
        _TABLE,
        sa.Column("pii_redaction_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        _TABLE,
        sa.Column("pii_counts_by_type", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "pii_counts_by_type")
    op.drop_column(_TABLE, "pii_redaction_count")
    op.drop_column(_TABLE, "char_count")
    op.drop_column(_TABLE, "page_count")
