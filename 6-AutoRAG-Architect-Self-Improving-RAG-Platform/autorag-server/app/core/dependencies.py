"""FastAPI dependency injection — shared across all routes."""

import uuid

from fastapi import Depends, Header, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser


async def get_trace_id(x_trace_id: str = Header(default="")) -> str:
    """Extracts or generates X-Trace-ID for request correlation."""
    return x_trace_id or str(uuid.uuid4())


async def get_organization_id(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> str:
    """Real multi-tenant scoping identity — derived from the verified JWT,
    never a client-supplied header (R-054, 24-Jul-2026 release audit).

    Previously trusted a raw `X-Organization-ID` header with no validation
    against the authenticated identity: an authenticated user could read or
    write any other organization's data by sending a different header value
    (confirmed exploitable via a live proof-of-concept — a fabricated,
    never-authenticated org UUID returned a real 200 with a scoped query
    result instead of a 401/403). FastAPI caches per-request dependencies,
    so this reuses the same `AuthenticatedUser` every route already resolves
    via `Depends(get_current_user)` — no route file needed to change.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user has no organization_id claim.",
        )
    return current_user.organization_id
