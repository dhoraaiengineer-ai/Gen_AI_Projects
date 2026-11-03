"""Add purpose column to golden_questions.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-26 00:00:00.000000 UTC

Closes a real gap found during the Evaluation Datasets page redesign: a
golden question's `question`/`reference_answer`/`expected_context` explain
*what* is being tested, but nothing explains *why* the question exists (what
failure mode it guards against). Adds a nullable `purpose` text field,
following the same nullable-free-text pattern already established by
`golden_questions.reviewer_notes` (migration 0017). Existing rows get NULL;
the UI shows an honest "Not documented yet" state rather than fabricating
placeholder copy.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("golden_questions", sa.Column("purpose", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("golden_questions", "purpose")
