"""Database integration: migrations at head, RLS everywhere, seed loaded, anchors visible in SQL.

Runs only when ``TEST_DATABASE_URL`` points at a migrated and seeded database, e.g. the local
container: ``postgresql+psycopg://postgres:finagent_local@127.0.0.1:5440/finagent``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from src.data.ingestion.seed import SEED_VERSION

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection[Any]]:
    assert URL
    with psycopg.connect(URL.replace("+psycopg", ""), prepare_threshold=None) as c:
        yield c


def test_migrations_at_head(conn: psycopg.Connection[Any]) -> None:
    row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row is not None
    assert row[0] == "0004"


def test_rls_enabled_on_every_public_table(conn: psycopg.Connection[Any]) -> None:
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity"
    ).fetchall()
    assert rows == []


def test_seed_version_matches_code(conn: psycopg.Connection[Any]) -> None:
    row = conn.execute("SELECT version FROM seed_state WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == SEED_VERSION


def test_pf_a_single_name_breach_visible_in_sql(conn: psycopg.Connection[Any]) -> None:
    row = conn.execute(
        """
        WITH latest AS (
          SELECT h.instrument_id, h.quantity, h.as_of_date
          FROM holdings h JOIN portfolios p ON p.id = h.portfolio_id
          WHERE p.code = 'PF-A' AND p.tenant_id = '0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01'
            AND h.as_of_date = (SELECT MAX(as_of_date) FROM holdings WHERE portfolio_id = p.id)
        ), valued AS (
          SELECT i.ticker, l.quantity * m.close AS value
          FROM latest l
          JOIN instruments i ON i.id = l.instrument_id
          JOIN market_data m ON m.instrument_id = l.instrument_id AND m.trade_date = l.as_of_date
        )
        SELECT ticker, value / SUM(value) OVER () AS weight FROM valued ORDER BY value DESC LIMIT 1
        """
    ).fetchone()
    assert row is not None
    assert row[0] == "NVTK"
    assert float(row[1]) > 0.25


def test_audit_log_is_append_only(conn: psycopg.Connection[Any]) -> None:
    with conn.transaction(force_rollback=True):
        conn.execute(
            "INSERT INTO audit_logs (tenant_id, action, decision, details) "
            "VALUES ('0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01', 'test', 'allow', '{}')"
        )
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("UPDATE audit_logs SET action = 'tampered'")


def test_every_tenant_table_has_isolation_policy(conn: psycopg.Connection[Any]) -> None:
    rows = conn.execute(
        """
        SELECT c.table_name FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'
          AND NOT EXISTS (SELECT 1 FROM pg_policies p
                          WHERE p.tablename = c.table_name AND p.policyname = 'tenant_isolation')
        """
    ).fetchall()
    assert rows == []
