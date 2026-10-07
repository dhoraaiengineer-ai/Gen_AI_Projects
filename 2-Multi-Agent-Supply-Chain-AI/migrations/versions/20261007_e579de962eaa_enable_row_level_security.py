"""enable row level security

Revision ID: e579de962eaa
Revises: aebdac3ccfbc
Create Date: 2026-10-07 09:12:55.855735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e579de962eaa'
down_revision: Union[str, Sequence[str], None] = 'aebdac3ccfbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Supabase exposes the public schema through PostgREST with the browser-visible publishable key.
# RLS with no policies denies anon/authenticated access; the backend connects as the table owner and bypasses RLS.
TABLES = ['products', 'inventory', 'sales', 'suppliers', 'supplier_products', 'carriers', 'purchase_orders', 'shipments', 'approvals', 'agent_events', 'notifications', 'notification_reads', 'conversations', 'messages', 'kb_sources', 'kb_chunks', 'kb_state', 'alembic_version']


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
