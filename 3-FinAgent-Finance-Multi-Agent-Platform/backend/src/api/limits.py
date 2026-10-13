"""Route guard = permission check + per-user rate limit for an endpoint group.

The ``X-RateLimit-*`` headers are added to every response by ``RequestContextMiddleware`` (also
for streaming responses); a 429 additionally carries ``Retry-After``.
"""

# No ``from __future__ import annotations``: FastAPI must resolve ``Depends(guard)`` (a local) at
# definition time.
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Request

from src.core.errors import RateLimited
from src.core.rate_limit import RateDecision
from src.security.auth import Principal, require_permission


def limited(permission: str | tuple[str, ...], group: str) -> Callable[..., Any]:
    """``permission``: one permission, or a tuple of which the caller needs any one."""
    permissions = (permission,) if isinstance(permission, str) else permission
    guard = require_permission(*permissions)

    async def dependency(
        request: Request, principal: Annotated[Principal, Depends(guard)]
    ) -> Principal:
        limiter = request.app.state.container.rate_limiter
        try:
            decision: RateDecision = await limiter.check(
                principal.tenant_id, principal.user_id, group
            )
        except RateLimited as exc:
            limit = limiter.limits[group].requests
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            }
            raise exc
        request.state.rate_limit_headers = decision.headers()
        return principal

    dependency.required_role = permissions  # type: ignore[attr-defined]  # architecture-test marker
    return dependency
