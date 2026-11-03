"""Integration tests for audit_log — D-4 acceptance criteria.

Uses real Supabase PostgreSQL (no mocks — Rule 80).
Each test is wrapped in a transaction that rolls back after the test,
keeping the audit_log table clean between runs.

Acceptance criteria verified here:
  [D-4-AC-1] INSERT succeeds for every approved event_type
  [D-4-AC-2] GET /api/v1/audit-log returns entries scoped to org
  [D-4-AC-3] GET filters by event_type correctly
  [D-4-AC-4] GET filters by run_id correctly
  [D-4-AC-5] Invalid event_type filter returns 400
  [D-4-AC-6] Cross-org isolation — org A cannot see org B entries
  [D-4-AC-7] DB-level UPDATE trigger raises exception (Layer 3 enforcement)
  [D-4-AC-8] DB-level DELETE trigger raises exception (Layer 3 enforcement)
  [D-4-AC-9] Unapproved event_type raises ValueError at repository level
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.main import app as _app
from app.models.audit_log import APPROVED_EVENT_TYPES
from app.repositories.audit_log_repository import AuditLogRepository

# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_headers(org_id: str | uuid.UUID, trace_id: str = "test-trace") -> dict:
    """Trace-ID header only -- organization scoping no longer comes from a
    client-supplied header (R-054 fix, 24-Jul-2026 release audit): a raw
    X-Organization-ID header used to be trusted with zero validation against
    the authenticated identity, letting any authenticated user read another
    org's audit log by changing this header. Kept for X-Trace-ID convenience;
    any X-Organization-ID value passed here is now ignored by the app."""
    return {"X-Trace-ID": trace_id}


@pytest.fixture
def as_org():
    """Override get_current_user for one test, simulating a real authenticated
    user in the given organization -- the correct way to test multi-tenant
    scoping post-R-054, since organization_id now comes from the verified
    identity, not a header. Auto-restores the real dependency after the test."""

    def _set(org_id: str | uuid.UUID) -> None:
        async def _fake_user() -> AuthenticatedUser:
            return AuthenticatedUser(
                user_id=str(uuid.uuid4()),
                email="test@example.com",
                organization_id=str(org_id),
                role="admin",
            )

        _app.dependency_overrides[get_current_user] = _fake_user

    yield _set
    _app.dependency_overrides.pop(get_current_user, None)


# ── Repository-level tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAuditLogRepository:
    """Direct repository tests — no HTTP layer."""

    async def test_insert_all_approved_event_types(self, db_session: AsyncSession) -> None:
        """[D-4-AC-1] Every approved event_type must be insertable."""
        repo = AuditLogRepository(db_session)
        org_id = uuid.uuid4()

        for event_type in APPROVED_EVENT_TYPES:
            entry = await repo.insert(
                event_type=event_type,
                payload={"test": True},
                organization_id=org_id,
            )
            assert entry.id is not None
            assert entry.event_type == event_type

    async def test_insert_unapproved_event_type_raises(self, db_session: AsyncSession) -> None:
        """[D-4-AC-9] Unapproved event_type is rejected before hitting the DB."""
        repo = AuditLogRepository(db_session)
        with pytest.raises(ValueError, match="Invalid event_type"):
            await repo.insert(
                event_type="not_a_real_event",
                payload={"test": True},
            )

    async def test_list_by_org_returns_only_own_entries(self, db_session: AsyncSession) -> None:
        """[D-4-AC-6] Entries from org A must not appear in org B's list."""
        repo = AuditLogRepository(db_session)
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()

        await repo.insert(event_type="pipeline_created", payload={}, organization_id=org_a)
        await repo.insert(event_type="pipeline_updated", payload={}, organization_id=org_b)

        results_a = await repo.list_by_org(organization_id=org_a)
        for entry in results_a:
            assert entry.organization_id == org_a

        results_b = await repo.list_by_org(organization_id=org_b)
        for entry in results_b:
            assert entry.organization_id == org_b

    async def test_list_by_org_filters_by_event_type(self, db_session: AsyncSession) -> None:
        """[D-4-AC-3] Event type filter returns only matching rows."""
        repo = AuditLogRepository(db_session)
        org_id = uuid.uuid4()

        await repo.insert(event_type="deploy_started", payload={}, organization_id=org_id)
        await repo.insert(event_type="deploy_completed", payload={}, organization_id=org_id)

        results = await repo.list_by_org(organization_id=org_id, event_type="deploy_started")
        assert all(e.event_type == "deploy_started" for e in results)

    async def test_list_by_run_id(self, db_session: AsyncSession) -> None:
        """[D-4-AC-4] run_id filter returns only entries for that run."""
        repo = AuditLogRepository(db_session)
        org_id = uuid.uuid4()
        run_id = uuid.uuid4()
        other_run_id = uuid.uuid4()

        await repo.insert(event_type="eval_started", payload={}, organization_id=org_id, run_id=run_id)
        await repo.insert(event_type="eval_completed", payload={}, organization_id=org_id, run_id=run_id)
        await repo.insert(event_type="eval_started", payload={}, organization_id=org_id, run_id=other_run_id)

        results = await repo.list_by_run_id(run_id=run_id, organization_id=org_id)
        assert len(results) == 2
        assert all(e.run_id == run_id for e in results)

    async def test_db_update_trigger_blocks_mutation(self, db_session: AsyncSession) -> None:
        """[D-4-AC-7] PL/pgSQL trigger raises EXCEPTION on UPDATE — Layer 3 enforcement."""
        from sqlalchemy.exc import ProgrammingError

        repo = AuditLogRepository(db_session)
        entry = await repo.insert(
            event_type="pipeline_created",
            payload={"initial": True},
        )
        await db_session.flush()

        with pytest.raises((ProgrammingError, Exception), match="INSERT ONLY"):
            await db_session.execute(
                text("UPDATE audit_log SET payload = :p WHERE id = :id"),
                {"p": '{"tampered": true}', "id": str(entry.id)},
            )

    async def test_db_delete_trigger_blocks_deletion(self, db_session: AsyncSession) -> None:
        """[D-4-AC-8] PL/pgSQL trigger raises EXCEPTION on DELETE — Layer 3 enforcement."""
        from sqlalchemy.exc import ProgrammingError

        repo = AuditLogRepository(db_session)
        entry = await repo.insert(
            event_type="pipeline_created",
            payload={},
        )
        await db_session.flush()

        with pytest.raises((ProgrammingError, Exception), match="INSERT ONLY"):
            await db_session.execute(
                text("DELETE FROM audit_log WHERE id = :id"),
                {"id": str(entry.id)},
            )


# ── API-level tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAuditLogAPI:
    """HTTP tests against GET /api/v1/audit-log."""

    async def test_list_returns_200_with_data(
        self, client: AsyncClient, db_session: AsyncSession, as_org
    ) -> None:
        """[D-4-AC-2] GET returns paginated entries for the caller's org."""
        org_id = uuid.uuid4()
        as_org(org_id)
        repo = AuditLogRepository(db_session)
        await repo.insert(event_type="ingest_started", payload={"file": "doc.pdf"}, organization_id=org_id)
        await db_session.commit()

        response = await client.get(
            "/api/v1/audit-log",
            headers=_org_headers(org_id, trace_id="d4-test"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["data"]["count"] >= 1
        assert body["request_id"] == "d4-test"
        assert any(e["event_type"] == "ingest_started" for e in body["data"]["items"])

    async def test_filter_by_event_type(
        self, client: AsyncClient, db_session: AsyncSession, as_org
    ) -> None:
        """[D-4-AC-3] event_type query param filters results."""
        org_id = uuid.uuid4()
        as_org(org_id)
        repo = AuditLogRepository(db_session)
        await repo.insert(event_type="deploy_started", payload={}, organization_id=org_id)
        await repo.insert(event_type="rollback_triggered", payload={}, organization_id=org_id)
        await db_session.commit()

        response = await client.get(
            "/api/v1/audit-log",
            params={"event_type": "deploy_started"},
            headers=_org_headers(org_id),
        )
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) >= 1  # non-vacuous: real data must actually be found
        assert all(item["event_type"] == "deploy_started" for item in items)

    async def test_invalid_event_type_returns_400(self, client: AsyncClient) -> None:
        """[D-4-AC-5] Unrecognised event_type returns 400 with helpful message."""
        org_id = uuid.uuid4()
        response = await client.get(
            "/api/v1/audit-log",
            params={"event_type": "totally_fake_event"},
            headers=_org_headers(org_id),
        )
        assert response.status_code == 400
        # main.py's http_exception_handler (Rule 35) normalizes every HTTPException
        # into {status, data, error, request_id} -- never FastAPI's raw {"detail": ...}.
        body = response.json()
        assert body["status"] == "error"
        error = body["error"]
        assert error["code"] == "INVALID_EVENT_TYPE"
        assert "valid_values" in error["details"]

    async def test_invalid_org_id_returns_400(self, client: AsyncClient, as_org) -> None:
        """organization_id (from the verified identity, not a header post-R-054)
        must be a valid UUID -- a malformed org claim on the JWT is rejected."""
        as_org("not-a-uuid")
        response = await client.get(
            "/api/v1/audit-log",
            headers={"X-Trace-ID": "test"},
        )
        assert response.status_code == 400

    async def test_missing_organization_claim_returns_403(self, client: AsyncClient) -> None:
        """R-054 fix (24-Jul-2026): an authenticated user with no organization_id
        claim at all is rejected with 403, not silently allowed through with an
        empty/None tenant scope."""

        async def _fake_user_no_org() -> AuthenticatedUser:
            return AuthenticatedUser(
                user_id=str(uuid.uuid4()), email="test@example.com", organization_id=None
            )

        _app.dependency_overrides[get_current_user] = _fake_user_no_org
        try:
            response = await client.get("/api/v1/audit-log")
        finally:
            _app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    async def test_cross_tenant_header_spoofing_is_ignored(
        self, client: AsyncClient, db_session: AsyncSession, as_org
    ) -> None:
        """R-054 regression test (24-Jul-2026 release audit, Critical finding).

        Before the fix: an authenticated user could read another organization's
        audit log entries by simply sending a different X-Organization-ID header
        -- confirmed exploitable via a live proof-of-concept during the audit
        (a fabricated, never-authenticated org UUID returned 200 with a scoped
        result instead of 401/403).

        This test authenticates as a real user in Org A, plants real data under
        a *different* Org B, then sends a request claiming to be Org B via the
        header. The fix must ignore the header entirely and return only Org A's
        (empty) results -- never Org B's real data.
        """
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()

        # Real data planted under Org B only.
        repo = AuditLogRepository(db_session)
        await repo.insert(event_type="deploy_completed", payload={}, organization_id=org_b)
        await db_session.commit()

        # Authenticate as Org A, but attempt to claim Org B via the header.
        as_org(org_a)
        response = await client.get(
            "/api/v1/audit-log",
            headers={"X-Organization-ID": str(org_b), "X-Trace-ID": "r054-poc"},
        )

        assert response.status_code == 200
        body = response.json()["data"]
        # Org B's real entry must NEVER appear -- the header claim is ignored.
        assert not any(
            item.get("organization_id") == str(org_b) for item in body["items"]
        ), "R-054 REGRESSION: cross-tenant data leaked via X-Organization-ID header spoofing"

    async def test_pagination_limit_and_offset(
        self, client: AsyncClient, db_session: AsyncSession, as_org
    ) -> None:
        """limit and offset params are respected."""
        org_id = uuid.uuid4()
        as_org(org_id)
        repo = AuditLogRepository(db_session)
        for _ in range(5):
            await repo.insert(event_type="pipeline_created", payload={}, organization_id=org_id)
        await db_session.commit()

        response = await client.get(
            "/api/v1/audit-log",
            params={"limit": 2, "offset": 0},
            headers=_org_headers(org_id),
        )
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 2
