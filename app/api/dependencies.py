import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container
from app.core.auth import AuthError, Principal, Role
from app.core.metrics import AUTH_FAILURES
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
    container: Container = Depends(get_container),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Authentication: who is calling? 401 if there's no valid token."""
    if container.verifier is None:
        return LOCAL_DEV_PRINCIPAL
    if credentials is None:
        raise _unauthorized("missing_token", "Sign in required")
    try:
        return container.verifier.verify(credentials.credentials)
    except AuthError as exc:
        logger.info("rejected token", extra={"reason": str(exc)})
        raise _unauthorized("invalid_token", "Invalid or expired token") from exc


def require_user(principal: Principal = Depends(get_principal)) -> Principal:
    """Authorization: any signed-in user."""
    return principal


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """Authorization: admins only. 403 means signed in but not allowed."""
    if not principal.is_admin:
        AUTH_FAILURES.labels("forbidden").inc()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return principal
