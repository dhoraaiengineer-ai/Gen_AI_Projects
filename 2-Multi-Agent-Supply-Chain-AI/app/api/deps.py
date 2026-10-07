"""FastAPI dependencies: services, authentication, role checks and rate limiting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request, Response

from app.container import Services
from app.core.context import user_id_var
from app.core.errors import Forbidden, Unauthorized
from app.core.rbac import Role, User


def get_services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


async def require_user(request: Request, services: Services = Depends(get_services)) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Sign in to continue.")
    if services.verifier is None:
        raise Unauthorized("Authentication is not configured.")
    user = services.verifier.verify(token)
    user_id_var.set(user.id)
    request.state.user = user
    return user


def require_role(role: Role) -> Callable[..., Awaitable[User]]:
    async def dep(user: User = Depends(require_user)) -> User:
        if not user.role.at_least(role):
            raise Forbidden(f"This action requires the {role.value} role.")
        return user

    return dep


require_analyst = require_role(Role.ANALYST)
require_approver = require_role(Role.APPROVER)
require_admin = require_role(Role.ADMIN)


def rate_limit(group: str) -> Callable[..., Awaitable[None]]:
    async def dep(response: Response, user: User = Depends(require_user), services: Services = Depends(get_services)) -> None:
        result = await services.rate_limiter.check(group, user.id)
        for k, v in result.headers().items():
            response.headers[k] = v

    return dep
