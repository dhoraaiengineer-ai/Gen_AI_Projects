"""Async engine and session factory.

Supabase's transaction pooler (port 6543) does not support prepared statements, so every psycopg
connection sets ``prepare_threshold=None``. Long-lived/session features (migrations, LangGraph
checkpointer, COPY seeding) use the session pooler URL instead.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from src.core.errors import Forbidden
from src.core.tenancy import current_tenant
from src.db.base import TenantScoped

logger = logging.getLogger(__name__)

SKIP_TENANT_FILTER = "skip_tenant_filter"  # execution option for audited system-wide jobs only


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state: ORMExecuteState) -> None:
    """Add ``tenant_id = <current tenant>`` to every ORM select/update/delete (ADR-026)."""
    if state.execution_options.get(SKIP_TENANT_FILTER):
        return
    if not (state.is_select or state.is_update or state.is_delete):
        return
    tenant = current_tenant()
    if tenant is None:
        if any(issubclass(m.class_, TenantScoped) for m in state.all_mappers):
            raise Forbidden("tenant-scoped query without a tenant in context")
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantScoped, lambda cls: cls.tenant_id == tenant, include_aliases=True
        )
    )


@event.listens_for(Session, "before_flush")
def _stamp_tenant(session: Session, flush_context: object, instances: object) -> None:
    """New tenant-scoped rows get the current tenant; a different explicit tenant is refused."""
    del flush_context, instances
    tenant = current_tenant()
    for obj in session.new:
        if not isinstance(obj, TenantScoped):
            continue
        explicit = getattr(obj, "tenant_id", None)
        if explicit is None:
            if tenant is None:
                raise Forbidden("cannot create tenant-scoped rows without a tenant in context")
            obj.tenant_id = tenant
        elif tenant is not None and explicit != tenant:
            raise Forbidden("cannot write rows for another tenant")


def use_selector_event_loop_on_windows() -> None:
    """Async psycopg cannot run on Windows' default Proactor loop."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined,unused-ignore]


def create_engine(url: str, *, pool_size: int = 5, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=pool_size,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"prepare_threshold": None, "connect_timeout": 10},
    )


@dataclass
class Database:
    """Owns the engine and session factory for the process."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    @classmethod
    def from_url(cls, url: str, *, pool_size: int = 5) -> Database:
        engine = create_engine(url, pool_size=pool_size)
        return cls(engine=engine, sessions=async_sessionmaker(engine, expire_on_commit=False))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Unit of work: commits on success, rolls back on error."""
        async with self.sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()
        logger.info("database engine disposed")
