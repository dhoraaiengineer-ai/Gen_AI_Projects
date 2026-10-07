import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container
from app.core.auth import AuthError, Principal, Role
from app.core.metrics import AUTH_FAILURES, RATE_LIMITED
from app.rag.service import RAGService

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False, description="Supabase Auth access token")

LOCAL_DEV_PRINCIPAL = Principal(user_id="local-dev", email=None, role=Role.ADMIN)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_service(request: Request) -> RAGService:
    return request.app.state.container.service


def _unauthorized(reason: str, detail: str) -> HTTPException:
    AUTH_FAILURES.labels(reason).inc()
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_principal(
    request: Request,
    container: Container = Depends(get_container),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Authentication: who is calling? 401 if there's no valid token."""
    if container.verifier is None:
        principal = LOCAL_DEV_PRINCIPAL
    elif credentials is None:
        raise _unauthorized("missing_token", "Sign in required")
    else:
        try:
            principal = container.verifier.verify(credentials.credentials)
        except AuthError as exc:
            logger.info("rejected token", extra={"reason": str(exc)})
            raise _unauthorized("invalid_token", "Invalid or expired token") from exc
    request.state.principal = principal  # for the per-request audit log line
    return principal


def require_user(principal: Principal = Depends(get_principal)) -> Principal:
    """Authorization: any signed-in user."""
    return principal


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """Authorization: admins only. 403 means signed in but not allowed."""
    if not principal.is_admin:
        AUTH_FAILURES.labels("forbidden").inc()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return principal


def rate_limit(bucket: str) -> Callable[..., None]:
    """Per-user limit for one group of endpoints (see app/core/ratelimit.py). Declare it after the auth
    dependency: it keys on the caller's user id, and unauthenticated calls are rejected before counting."""

    def check(request: Request, response: Response, principal: Principal = Depends(get_principal)) -> None:
        limiter = request.app.state.rate_limiters.get(bucket)
        if limiter is None:
            return
        decision = limiter.hit(principal.user_id)
        headers = {"X-RateLimit-Limit": str(decision.limit), "X-RateLimit-Remaining": str(decision.remaining)}
        if not decision.allowed:
            RATE_LIMITED.labels(bucket).inc()
            logger.info("rate limited", extra={"bucket": bucket, "user_id": principal.user_id})
            detail = f"Too many requests: limit is {decision.limit} per minute. Try again in {decision.retry_after}s."
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
                headers={**headers, "Retry-After": str(decision.retry_after)},
            )
        response.headers.update(headers)

    return check
