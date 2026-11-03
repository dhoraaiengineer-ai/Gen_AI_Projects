"""Enable pgcrypto and pgvector extensions.

Revision ID: 0001
Revises: —
Create Date: 2026-05-26 00:00:00.000000 UTC

Extensions required:
  - pgcrypto : gen_random_uuid() used by legacy helpers
  - vector   : pgvector — Supabase Vector (768-dim for Gemini Embedding 2)
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # pgcrypto — provides gen_random_uuid(), crypt(), etc.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # pgvector — Supabase Vector; used by autorag_{pipeline_id}_{version} tables
    # NOTE: pgvector tables are NOT managed by Alembic — they are created dynamically
    # by the Builder agent. This extension must exist before any vector table is created.
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')


def downgrade() -> None:
    # Dropping pgvector would destroy ALL vector tables — not safe in staging/prod.
    # Downgrade intentionally left as no-op; run manually if required.
    pass
