"""Shared utilities for services — ID validation.

Version 4 (20-Jul-2026): table_name() removed along with the per-version
dynamic table convention it built (see migration 0016) -- pipeline_id and
pipeline_version are now bound query parameters against the single shared
pipeline_chunks table, not interpolated into a SQL identifier, so this
allowlist is no longer a SQL-injection boundary. Kept as a basic input
sanity check.
"""

import re

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def validate_id(value: str, label: str) -> None:
    """Reject IDs that contain characters outside the safe allowlist (Rule 70)."""
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(
            f"Invalid {label} '{value}' — only [a-zA-Z0-9_-] allowed"
        )
