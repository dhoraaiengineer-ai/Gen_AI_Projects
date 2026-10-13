"""Ingest a folder into the knowledge base for one tenant (idempotent: unchanged files are skipped).

    uv run python -m scripts.ingest_kb                       # knowledge/samples → Northwind
    uv run python -m scripts.ingest_kb --tenant contoso
    uv run python -m scripts.ingest_kb --strategy parent_child --force

Metadata per file comes from ``knowledge/manifest.json`` (doc_type, classification, ticker, ...).
Cost: one embedding call per changed file (~2k tokens for the samples).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from src.config.settings import REPO_ROOT, get_settings
from src.container import Container
from src.core.logging import configure_logging
from src.core.tenancy import DEMO_TENANT_ID, SECOND_TENANT_ID, tenant_scope
from src.rag.chunking import STRATEGIES
from src.rag.types import DocumentMeta

TENANTS = {"northwind": DEMO_TENANT_ID, "contoso": SECOND_TENANT_ID}


def _meta(raw: dict[str, object]) -> DocumentMeta:
    def d(key: str) -> date | None:
        value = raw.get(key)
        return date.fromisoformat(str(value)) if value else None

    return DocumentMeta(
        doc_type=str(raw.get("doc_type", "internal")),
        classification=str(raw.get("classification", "internal")),
        ticker=str(raw["ticker"]) if raw.get("ticker") else None,
        fiscal_period=str(raw["fiscal_period"]) if raw.get("fiscal_period") else None,
        effective_date=d("effective_date"),
        expiry_date=d("expiry_date"),
    )


async def run(folder: Path, tenant: str, strategy: str, force: bool) -> int:
    files = sorted(p for p in folder.iterdir() if p.is_file())  # noqa: ASYNC240 — CLI startup
    manifest = json.loads((folder.parent / "manifest.json").read_text(encoding="utf-8"))
    container = Container.build(get_settings())
    failures = 0
    try:
        kb = container.knowledge
        with tenant_scope(TENANTS[tenant]):
            for path in files:
                meta = _meta(manifest.get(path.name, {}))
                if force:
                    await kb.repo.record_failure(path.name, meta, "re-ingest", "-")
                result = await kb.ingestion.ingest_bytes(
                    path.read_bytes(), path.name, meta, strategy=strategy
                )
                failures += result.status == "failed"
                print(
                    f"{result.status:9s} {path.name:40s} chunks={result.chunks:3d} "
                    f"embedded={result.embedded:3d} {result.seconds:5.1f}s"
                    + (f"  ! {result.error}" if result.error else "")
                    + (f"  ({'; '.join(result.warnings)})" if result.warnings else "")
                )
            version, model = await kb.repo.kb_state()
            print(f"\nKB version {version} · embedding model {model}")
    finally:
        await container.aclose()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=REPO_ROOT / "knowledge" / "samples")
    parser.add_argument("--tenant", choices=sorted(TENANTS), default="northwind")
    parser.add_argument("--strategy", choices=STRATEGIES, default="auto")
    parser.add_argument("--force", action="store_true", help="re-embed even unchanged files")
    args = parser.parse_args()
    configure_logging()
    code = asyncio.run(
        run(args.folder, args.tenant, args.strategy, args.force),
        loop_factory=asyncio.SelectorEventLoop,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
