"""Audit log on a real database: stored per tenant, PII redacted. Needs ``TEST_DATABASE_URL``."""

from __future__ import annotations

import os
import uuid

import pytest

from src.core.tenancy import DEMO_TENANT_ID, SECOND_TENANT_ID, tenant_scope
from src.data.repositories.audit import AuditRepository
from src.db.session import Database
from src.security.audit import AuditEvent, AuditService

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


async def test_audit_rows_are_tenant_scoped_and_redacted() -> None:
    assert URL
    db = Database.from_url(URL)
    repo = AuditRepository(db)
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    try:
        with tenant_scope(DEMO_TENANT_ID):
            await AuditService(repo).record(
                AuditEvent(
                    "guardrail.input",
                    "block",
                    "prompt_injection",
                    request_id=request_id,
                    user_role="analyst",
                    details={"contact": "jo@example.com"},
                )
            )
            rows = [
                r
                for r in await repo.recent(action="guardrail.input")
                if r["requestId"] == request_id
            ]
        assert len(rows) == 1 and rows[0]["decision"] == "block"
        assert rows[0]["details"] == {"contact": "[EMAIL]"}
        with tenant_scope(SECOND_TENANT_ID):
            other = await repo.recent(action="guardrail.input")
        assert all(r["requestId"] != request_id for r in other)
    finally:
        await db.dispose()
