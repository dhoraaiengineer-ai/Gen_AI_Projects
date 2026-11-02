"""Build upload-ready SYNTHETIC PDFs that are NOT in the base corpus: data/uploads/src/*.md → data/uploads/*.pdf.

Use them to test Admin → Knowledge upload; evals/upload_qa.jsonl is their golden set (run after uploading).
Upload each with doc_id = the file name (citations become "<doc_id>#<section>"):
  volt_winter_guide.pdf  → type owner_manual, visibility owner, model Volt, version 2026.2
  TSB-AR-2026-01.pdf     → type tsb,          visibility staff, model Aria, version 2026.1

Usage (from autoserve-server/): uv run python -m scripts.generate_upload_docs
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.generate_knowledge import parse_markdown, render_pdf

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "uploads" / "src"
OUT = ROOT / "data" / "uploads"


def main() -> int:
    for src in sorted(SRC.glob("*.md")):
        meta, sections = parse_markdown(src)
        target = OUT / f"{meta['doc_id']}.pdf"
        render_pdf(meta, sections, target)
        print(
            f"{target.relative_to(ROOT)} — {meta['doc_type']}, {meta['visibility']}, model {meta['model']}, "
            f"{len(sections)} section(s)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
