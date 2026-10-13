"""Multi-tenancy (ADR-026): the current tenant for this request/task.

A tenant is an asset-management firm. The tenant id comes only from the authenticated user's JWT
(``app_metadata.tenant_id``) or, for system jobs, from an explicit ``tenant_scope(...)``. Every
tenant-scoped query is filtered automatically (``src/db/session.py``); code never passes tenant
ids around by hand.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from src.core.errors import Forbidden

# Fixed ids for the seeded demo tenants (fictional firms).
DEMO_TENANT_ID = uuid.UUID("0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01")  # Northwind Asset Management
SECOND_TENANT_ID = uuid.UUID("0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a02")  # Contoso Capital

_current_tenant: ContextVar[uuid.UUID | None] = ContextVar("tenant_id", default=None)


def current_tenant() -> uuid.UUID | None:
    return _current_tenant.get()


def require_tenant() -> uuid.UUID:
    tenant = _current_tenant.get()
    if tenant is None:
        raise Forbidden("no tenant in context")
    return tenant


def set_tenant(tenant_id: uuid.UUID | str | None) -> object:
    """Set the tenant for the current context; returns a token for :func:`reset_tenant`."""
    value = uuid.UUID(str(tenant_id)) if tenant_id is not None else None
    return _current_tenant.set(value)


def reset_tenant(token: object) -> None:
    _current_tenant.reset(token)  # type: ignore[arg-type]


@contextmanager
def tenant_scope(tenant_id: uuid.UUID | str) -> Iterator[uuid.UUID]:
    """Run a block as ``tenant_id`` (system jobs, seeding, tests)."""
    token = set_tenant(tenant_id)
    try:
        yield uuid.UUID(str(tenant_id))
    finally:
        reset_tenant(token)
