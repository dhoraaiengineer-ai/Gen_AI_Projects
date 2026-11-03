"""Add 'draft' to ck_pipelines_status.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-16 00:00:00.000000 UTC

The Configurator wizard's step 2 ("Document Sources") let a user click
"Upload PDF/DOCX/TXT" before the pipeline existed -- creation only happened
at step 6 ("Launch Pipeline"). That sent the user to /documents with no
pipeline_id to attach the upload to. Fix: create the pipeline immediately
after step 1 in a new 'draft' status, so every subsequent step (including
document upload) operates against a real pipeline from the start. Full
lifecycle management (Resume/Delete Draft, richer states, dashboard draft
UI) is explicitly deferred to post-MVP -- see PLAN.md Section 11 Out of
Scope, entry dated 16-Jul-2026.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None

_OLD_STATUSES = "('pending','running','ready','failed','decommissioned')"
_NEW_STATUSES = "('draft','pending','running','ready','failed','decommissioned')"


def upgrade() -> None:
    op.drop_constraint("ck_pipelines_status", "pipelines", type_="check")
    op.create_check_constraint(
        "ck_pipelines_status",
        "pipelines",
        sa.text(f"status IN {_NEW_STATUSES}").text,
    )


def downgrade() -> None:
    op.drop_constraint("ck_pipelines_status", "pipelines", type_="check")
    op.create_check_constraint(
        "ck_pipelines_status",
        "pipelines",
        sa.text(f"status IN {_OLD_STATUSES}").text,
    )
