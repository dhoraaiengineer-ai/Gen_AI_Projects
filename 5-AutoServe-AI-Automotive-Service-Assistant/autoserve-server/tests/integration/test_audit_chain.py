"""P1-4: audit_log is append-only (DB trigger) and tampering is detected by verify_chain()."""

from __future__ import annotations

import asyncpg
import httpx
import pytest

from tests.conftest import LoginFn

pytestmark = pytest.mark.integration

ADMIN = "admin@autoserve.example.test"


async def _verify(api: httpx.AsyncClient, login: LoginFn) -> dict[str, object]:
    resp = await api.get("/api/v1/admin/audit/verify", headers=await login(ADMIN))
    assert resp.status_code == 200
    return dict(resp.json()["data"])


async def test_seeded_chain_is_intact(api: httpx.AsyncClient, login: LoginFn) -> None:
    result = await _verify(api, login)
    assert result["intact"] is True
    assert int(str(result["checked"])) > 40  # seed transitions + logins
    assert result["first_broken_seq"] is None


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_log SET action = 'x' WHERE seq = (SELECT min(seq) FROM audit_log)",
        "DELETE FROM audit_log WHERE seq = (SELECT min(seq) FROM audit_log)",
        "TRUNCATE audit_log",
    ],
)
async def test_update_delete_truncate_are_blocked(db_conn: asyncpg.Connection, sql: str) -> None:
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError, match="append-only"):
        await db_conn.execute(sql)


async def test_tampering_is_detected_and_reported(
    api: httpx.AsyncClient, login: LoginFn, db_conn: asyncpg.Connection
) -> None:
    target = await db_conn.fetchrow("SELECT seq, payload FROM audit_log ORDER BY seq OFFSET 5 LIMIT 1")
    assert target is not None
    # Simulate an attacker with table-owner rights who disables the trigger and edits history.
    await db_conn.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_log_immutable")
    try:
        await db_conn.execute(
            'UPDATE audit_log SET payload = payload || \'{"to": "CLOSED"}\'::jsonb WHERE seq = $1', target["seq"]
        )
        result = await _verify(api, login)
        assert result["intact"] is False
        assert result["first_broken_seq"] == target["seq"]
    finally:
        await db_conn.execute(
            "UPDATE audit_log SET payload = $1::jsonb WHERE seq = $2", target["payload"], target["seq"]
        )
        await db_conn.execute("ALTER TABLE audit_log ENABLE TRIGGER audit_log_immutable")
    assert (await _verify(api, login))["intact"] is True


async def test_every_public_table_has_row_level_security(db_conn: asyncpg.Connection) -> None:
    """Supabase Data API lockdown (migration b7c1d2e3f405): no public table may be left without RLS."""
    missing = await db_conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity")
    assert [r["tablename"] for r in missing] == []
