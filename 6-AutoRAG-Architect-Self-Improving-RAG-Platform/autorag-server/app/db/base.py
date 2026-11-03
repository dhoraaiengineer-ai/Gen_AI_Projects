"""Backward-compatible re-export of the canonical declarative ``Base``.

The single source of truth for ORM metadata is :mod:`app.models.base`.
This module is kept as a shim so existing imports
(``from app.db.base import Base``) resolve to the **same** ``Base`` object —
avoiding the classic "two ``DeclarativeBase`` instances = two ``MetaData``
registries" bug, where Alembic autogenerate only sees half the tables.

Do not declare a new ``DeclarativeBase`` here. Import models from
:mod:`app.models` so every table registers on one shared metadata.
"""

from app.models.base import Base

__all__ = ["Base"]
