"""Ingest a folder of trusted documents using its manifest.yaml (provenance per file).
Unchanged files are skipped (content-hash registry); only changed chunks are re-embedded.

Usage: python scripts/ingest_corpus.py [data/synthetic/corpus] [--dry-run]
  --dry-run   load and chunk only; reports chunk counts and the embedding calls a real run would make
"""

from __future__ import annotations

import logging
import math
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.container import build_container
from app.core.logging import configure_logging
from app.rag.chunking import Chunker
from app.rag.ingest import EMBED_BATCH, Provenance
from app.rag.loaders import load_document
from app.rag.ocr import RapidOcrEngine

logger = logging.getLogger("ingest_corpus")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = Path(args[0] if args else "data/synthetic/corpus")
    dry = "--dry-run" in sys.argv
    settings = get_settings()
    configure_logging("WARNING", "text")
    manifest = yaml.safe_load((folder / "manifest.yaml").read_text(encoding="utf-8"))["documents"]

    if dry:
        chunker = Chunker(settings.chunk_strategy, chunk_size=settings.chunk_size)
        ocr = RapidOcrEngine()
        total = calls = 0
        for name in manifest:
            n = len(chunker.chunk("dry", load_document(name, (folder / name).read_bytes(), ocr)).chunks)
            total += n
            calls += math.ceil(n / EMBED_BATCH)
            print(f"{name:40} chunks={n}")
        print(
            f"\nTOTAL chunks={total}  embedding calls on first ingest ~{calls} (one per batch of {EMBED_BATCH})"
        )
        return

    ingest = build_container(settings).ingest
    for name, meta in manifest.items():
        report = ingest.ingest_trusted(name, (folder / name).read_bytes(), Provenance(**meta), actor_id="cli")
        print(
            f"{name:40} {report.status:9} chunks={report.chunks_total:3} embedded={report.embedded:3} "
            f"deleted={report.deleted:3} ocr={report.ocr_sections}"
        )


if __name__ == "__main__":
    main()
