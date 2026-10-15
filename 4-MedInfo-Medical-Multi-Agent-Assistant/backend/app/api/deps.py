"""Auth dependencies. Every route declares one of require_user / require_clinician / require_admin
(public routes are deliberate, commented exceptions)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container
from app.core.auth import AuthError, Principal

_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


def _principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    container: Container = Depends(get_container),
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sign in required.", headers={"WWW-Authenticate": "Bearer"}
        )
    if container.verifier is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured.")
    try:
        principal = container.verifier.verify(creds.credentials)
        request.state.user_id = principal.user_id  # read by the per-request audit line
        return principal
    except AuthError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired session.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _require(role: str) -> Callable[..., Principal]:
    def dep(principal: Principal = Depends(_principal)) -> Principal:
        if not principal.has_role(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this.")
        return principal

    return dep


require_user = _require("user")
require_clinician = _require("clinician")
require_admin = _require("admin")
