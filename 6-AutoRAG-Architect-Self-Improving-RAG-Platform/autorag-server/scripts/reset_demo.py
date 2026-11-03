"""Reset all runtime/demo data while preserving schema, users, and audit history.

Truncates the 9 runtime tables (pipelines, pipeline_versions, documents,
evaluation_runs, retrieval_chunks, experiment_runs, deployments,
agent_metrics, pipeline_chunks) and drops any leftover legacy dynamic
pgvector table (autorag_{pipeline_id}_{version} -- pre-Version-4.0 pipelines
only; migration 0016 replaced this convention with the single shared
pipeline_chunks table, truncated directly below like every other runtime
table).

Never touches: organizations, users, alembic_version, audit_log (unless
--include-audit-log is passed and confirmed).

Usage:
    ENVIRONMENT=local uv run python scripts/reset_demo.py
    uv run python scripts/reset_demo.py --force              # non-local env
    uv run python scripts/reset_demo.py --include-audit-log  # also wipe audit_log
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine

RUNTIME_TABLES = [
    "deployments",
    "experiment_runs",
    "retrieval_chunks",
    "evaluation_runs",
    "documents",
    "pipeline_versions",
    "pipelines",
    "agent_metrics",
    "pipeline_chunks",  # Version 4.0 (migration 0016) -- shared vector-chunk table
]


async def _row_counts(conn, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        result = await conn.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608 -- table names are the fixed RUNTIME_TABLES list, not user input
        counts[table] = result.scalar_one()
    return counts


async def _drop_legacy_vector_tables() -> list[str]:
    """Drop any leftover autorag_{pipeline_id}_{version} table from before
    Version 4.0 (migration 0016 replaced this convention with the shared
    pipeline_chunks table, which is truncated via RUNTIME_TABLES instead).
    pipeline_versions.vector_table_name no longer names a real physical
    table (it's a partition label, "pipeline_chunks:{id}:v{n}") so it is
    NOT used as a discovery source here -- information_schema is the only
    real source of truth for tables that still physically exist."""
    dropped: list[str] = []
    async with engine.connect() as conn:
        orphans = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE 'autorag\\_%' ESCAPE '\\'"
            )
        )
        legacy_tables = {row[0] for row in orphans.fetchall()}

        for table_name in sorted(legacy_tables):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))  # noqa: S608 -- table_name sourced only from information_schema, never user input
            dropped.append(table_name)
        await conn.commit()
    return dropped


async def reset_demo(include_audit_log: bool) -> None:
    async with engine.connect() as conn:
        before = await _row_counts(conn, RUNTIME_TABLES + (["audit_log"] if include_audit_log else []))

    print("[INFO] Row counts before reset:")
    for table, count in before.items():
        print(f"  {table}: {count}")

    dropped_vector_tables = await _drop_legacy_vector_tables()
    print(f"[INFO] Dropped {len(dropped_vector_tables)} legacy per-version pgvector table(s).")

    tables_to_truncate = RUNTIME_TABLES + (["audit_log"] if include_audit_log else [])
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"TRUNCATE {', '.join(tables_to_truncate)} RESTART IDENTITY CASCADE")  # noqa: S608 -- fixed table list, not user input
        )
        await session.commit()

    print(f"[DONE] Truncated: {', '.join(tables_to_truncate)}")
    if not include_audit_log:
        print("[SKIP] audit_log preserved (pass --include-audit-log to also clear it).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Allow running outside ENVIRONMENT=local.")
    parser.add_argument("--include-audit-log", action="store_true", help="Also truncate audit_log (requires typed confirmation).")
    args = parser.parse_args()

    if not settings.is_local and not args.force:
        print(f"[ERROR] Refusing to run against ENVIRONMENT={settings.environment!r}. Pass --force to override.")
        sys.exit(1)

    if args.include_audit_log:
        answer = input("Type 'yes' to confirm permanently clearing audit_log (INSERT-only compliance trail): ")
        if answer.strip().lower() != "yes":
            print("[ABORTED] audit_log not cleared.")
            sys.exit(1)

    asyncio.run(reset_demo(include_audit_log=args.include_audit_log))


if __name__ == "__main__":
    main()
