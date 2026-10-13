"""Load data/sample_docs into the knowledge base. Idempotent: unchanged files make no embedding calls.

uv run python scripts/ingest_sample_docs.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.compat import use_compatible_event_loop
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import Database
from app.rag.ingest import IngestRequest, IngestService
from app.rag.providers import ResilientEmbeddings, TesseractOcr

DOCS = Path(__file__).resolve().parents[1] / "data" / "sample_docs"


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)
    try:
        ocr = TesseractOcr(settings.ocr_languages)
    except Exception:
        ocr = None
    db = Database(settings.sqlalchemy_url(), pool_size=2)
    service = IngestService(db, ResilientEmbeddings(settings), settings.kb_collection, ocr, settings.max_upload_mb * 1_000_000)
    try:
        for path in sorted(DOCS.iterdir()):
            if path.is_file():
                result = await service.ingest(IngestRequest(filename=path.name, data=path.read_bytes(), uploaded_by="Sample data loader"))
                print(f"{result.status:9} +{result.chunks_added:<3} {path.name} {result.error or ''}")
    finally:
        await db.dispose()


if __name__ == "__main__":
    use_compatible_event_loop()
    asyncio.run(main())
