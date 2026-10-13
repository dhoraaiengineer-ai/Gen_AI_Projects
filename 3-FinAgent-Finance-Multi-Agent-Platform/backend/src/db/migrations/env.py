"""Alembic environment: runs migrations synchronously on the session pooler (5432)."""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import src.db.models  # noqa: F401  (registers tables)
from src.config.settings import get_settings
from src.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def _url() -> str:
    """``alembic -x url=...`` (local/test databases) > settings' session pooler URL."""
    override = context.get_x_argument(as_dictionary=True).get("url")
    return (
        override or config.get_main_option("sqlalchemy.url") or get_settings().session_database_url
    )


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _url(), poolclass=pool.NullPool, connect_args={"prepare_threshold": None}
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
