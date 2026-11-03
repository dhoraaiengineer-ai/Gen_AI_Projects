"""Backward-compatible re-export of the canonical session factory.

The engine and ``AsyncSession`` factory now live in
:mod:`app.core.database` (per the Team-5 D-3 starter-kit acceptance
criteria). This shim keeps existing imports
(``from app.db.session import get_db`` / ``AsyncSessionLocal`` /
``async_session_factory``) working unchanged.
"""

from app.core.database import (
    AsyncSessionLocal,
    async_session_factory,
    engine,
    get_db,
)

__all__ = [
    "engine",
    "AsyncSessionLocal",
    "async_session_factory",
    "get_db",
]
