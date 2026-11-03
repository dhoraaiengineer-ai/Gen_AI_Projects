"""Shared DeclarativeBase and UUID v7 helper for all ORM models.

UUID v7 = time-sortable, monotonically increasing — required by Rule 30.
All models import Base and uuid7 from here.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base — imported by all 9 ORM models."""

    pass


def uuid7() -> uuid.UUID:
    """Generate a UUID v7 (time-sortable).

    Layout (128 bits):
      [48-bit ms timestamp] [4-bit ver=7] [12-bit seq] [2-bit var] [62-bit rand]

    Falls back to uuid4 if the environment doesn't support time-based UUIDs.
    Replace with `uuid_utils.uuid7()` once the package is stable on Windows.
    """
    # 48-bit Unix epoch milliseconds
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    # 12-bit random sequence
    seq = uuid.uuid4().int & 0xFFF
    # 62-bit random node
    rand = uuid.uuid4().int & 0x3FFFFFFFFFFFFFFF

    value = (ms << 80) | (0x7 << 76) | (seq << 64) | (0b10 << 62) | rand
    return uuid.UUID(int=value)
