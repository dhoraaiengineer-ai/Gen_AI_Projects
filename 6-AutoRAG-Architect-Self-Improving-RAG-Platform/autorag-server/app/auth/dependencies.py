"""Authentication dependencies -- Supabase JWT verification."""

from __future__ import annotations

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.auth.schemas import AuthenticatedUser
from app.core.config import get_settings


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    """Resolve authenticated user by verifying the Supabase-issued JWT.

    Supabase signs access tokens with HS256 using the JWT secret from the
    project settings page. The secret is loaded from SUPABASE_JWT_SECRET (env).

    JWT claims used:
      sub             -- user UUID (required)
      email           -- user email
      app_metadata    -- may contain 'organization_id' and 'role'
      user_metadata   -- fallback for 'organization_id' and 'role'

    Raises HTTP 401 on missing header, invalid format, or JWT verification failure.
    Raises HTTP 500 if SUPABASE_JWT_SECRET is not configured (startup should have
    caught this -- fail loudly here in case it slipped through).
    """
    settings = get_settings()

    # Local dev bypass -- skip JWT verification so demo runs without Supabase auth.
    # The mock user's organization_id matches NEXT_PUBLIC_DEFAULT_ORG_ID in client .env.
    if settings.environment == "local":
        return AuthenticatedUser(
            user_id="00000000-0000-0000-0000-000000000001",
            email="dev@local",
            organization_id="00000000-0000-0000-0000-000000000001",
            role="admin",
        )

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len("Bearer "):]

    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server JWT configuration missing.",
        )

    try:
        payload: dict = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Supabase JWTs omit aud in some configs
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim.",
        )

    email: str = payload.get("email") or ""

    # organization_id may live in app_metadata (service-role injection) or
    # user_metadata (client-side custom claim) or as a top-level claim.
    app_meta: dict = payload.get("app_metadata") or {}
    user_meta: dict = payload.get("user_metadata") or {}
    organization_id: str | None = (
        app_meta.get("organization_id")
        or user_meta.get("organization_id")
        or payload.get("organization_id")
    )

    role: str = (
        app_meta.get("role")
        or user_meta.get("role")
        or payload.get("role")
        or "viewer"
    )

    return AuthenticatedUser(
        user_id=user_id,
        email=email,
        organization_id=organization_id,
        role=role,
    )
