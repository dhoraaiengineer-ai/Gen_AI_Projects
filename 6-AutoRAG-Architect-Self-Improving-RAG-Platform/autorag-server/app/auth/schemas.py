"""Authentication and authorization schemas."""

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Authenticated Supabase user context."""

    user_id: str
    email: str

    organization_id: str | None = None
    role: str | None = None

    is_active: bool = True
    is_superuser: bool = False
