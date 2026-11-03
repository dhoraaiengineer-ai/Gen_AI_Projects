"""Alembic migration environment."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

# Importing the package registers all 9 ORM models on Base.metadata,
# so autogenerate sees the full schema (single canonical metadata).
from app.models import Base  # noqa: F401

# ─────────────────────────────────────────────────────────────
# Alembic Config
# ─────────────────────────────────────────────────────────────

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ─────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────

target_metadata = Base.metadata

# ─────────────────────────────────────────────────────────────
# Offline Migrations
# ─────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ─────────────────────────────────────────────────────────────
# Online Migrations
# ─────────────────────────────────────────────────────────────


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Execute migrations."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run async migrations."""

    connectable = create_async_engine(
        settings.database_url,
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations online."""

    asyncio.run(run_async_migrations())


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
