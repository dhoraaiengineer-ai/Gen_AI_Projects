"""Load the synthetic dataset (idempotent). Uses the session pooler URL.

Usage: uv run python -m scripts.seed [--force] [--url postgresql+psycopg://...]
"""

from __future__ import annotations

import argparse
import json

from src.config.settings import get_settings
from src.core.logging import configure_logging
from src.data.ingestion.seed import seed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="reload even if the version matches")
    parser.add_argument("--url", help="override the database URL (default: session pooler)")
    args = parser.parse_args()
    configure_logging("INFO")
    report = seed(args.url or get_settings().session_database_url, force=args.force)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
