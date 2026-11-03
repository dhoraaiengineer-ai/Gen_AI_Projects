"""Async SQLAlchemy engine + session factory (canonical location).

This is the single source of truth for the database engine and the
``AsyncSession`` factory. ``app.db.session`` re-exports these names for
backward compatibility with existing imports.

Usage:
    from app.core.database import get_db          # FastAPI dependency
    from app.core.database import AsyncSessionLocal  # manual session
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# SQLAlchemy Async Engine
# ─────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=settings.is_local,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
)

# ─────────────────────────────────────────────────────────────
# Async Session Factory
# ─────────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Alias used by the health-check route (api.py imports this name).
async_session_factory = AsyncSessionLocal


# ─────────────────────────────────────────────────────────────
# FastAPI Dependency
# ─────────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session per request.

    Commits automatically on success, rolls back on failure.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
