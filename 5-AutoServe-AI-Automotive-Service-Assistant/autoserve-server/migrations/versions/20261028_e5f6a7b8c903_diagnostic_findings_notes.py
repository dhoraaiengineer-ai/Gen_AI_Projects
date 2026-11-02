"""diagnostic_findings.notes — technician free-text notes on a recorded finding (P3-2)

Revision ID: e5f6a7b8c903
Revises: d4e5f6a7b802
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c903"
down_revision: str | None = "d4e5f6a7b802"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("diagnostic_findings", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("diagnostic_findings", "notes")
