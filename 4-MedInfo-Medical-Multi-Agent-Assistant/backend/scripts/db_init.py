"""Create the database schema (idempotent): pgvector extension, PGVector tables and collections,
the full-text-search column and indexes, and the app tables.

Usage: python scripts/db_init.py            (uses DATABASE_URL from the environment / .env)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.core.logging import configure_logging
from app.rag.providers import init_database, make_engine


def main() -> None:
    settings = get_settings()
    configure_logging("INFO", "text")
    if settings.database_url is None:
        sys.exit("DATABASE_URL is not set")
    engine = make_engine(settings.database_url, pool_size=1)
    init_database(engine, list(settings.collection_names()), settings.embedding_dimensions)
    logging.getLogger(__name__).info("done")


if __name__ == "__main__":
    main()
