"""Generate the synthetic corpus and ingest it (make ingest). Idempotent: re-running adds nothing new.

Usage (from autoserve-server/): uv run python -m scripts.ingest
"""

from __future__ import annotations

import asyncio
import sys

from app.core.db import get_sessionmaker
from app.core.security import SYSTEM_ACTOR
from app.rag.embeddings import get_embedder
from app.rag.ingest import ingest_corpus
from app.services.audit import AuditService
from scripts.generate_knowledge import OUT, build


async def main() -> int:
    build()
    async with get_sessionmaker()() as session, session.begin():
        report = await ingest_corpus(session, get_embedder(), OUT)
        await AuditService(session).record(
            SYSTEM_ACTOR,
            "knowledge.ingested",
            "knowledge",
            None,
            {k: v for k, v in report.__dict__.items() if k != "notes"},
        )
    print("ingest:", {k: v for k, v in report.__dict__.items() if k != "notes"})
    for note in report.notes:
        print("  note:", note)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
