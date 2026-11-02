"""Build the SYNTHETIC knowledge corpus (P1-5): data/knowledge/src/*.md → watermarked PDFs + manifest.json + CSVs.

Source format (Markdown):
  front matter (YAML) with doc_id, title, doc_type, model, model_year_from/to, visibility, version (+ TSB/recall fields)
  `## <number> <title> [safety] [stop]` starts a section; body = paragraphs, `- ` bullets, `1. ` steps, pipe tables.
Each section heading is rendered as `§ <number> <title>` so ingestion can split on structure. PDFs are byte-for-byte
reproducible (reportlab invariant mode). Every page carries the SYNTHETIC watermark.

Usage (from autoserve-server/): uv run python -m scripts.generate_knowledge
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import yaml
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

rl_config.invariant = 1  # deterministic PDF bytes (no timestamps / random IDs)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "knowledge" / "src"
OUT = ROOT / "data" / "knowledge"
WATERMARK = "SYNTHETIC — FOR DEMO ONLY"
SECTION_MARK = "§"
_HEADING = re.compile(r"^##\s+(?P<number>\S+)\s+(?P<title>.+?)\s*(?P<tags>(\[(safety|stop)\]\s*)*)$")
_SUBDIRS = {"tsb": "tsb", "recall": "recalls"}


@dataclass
class Section:
    number: str
    title: str
    safety_critical: bool
    stop_required: bool
    lines: list[str] = field(default_factory=list)


def parse_markdown(path: Path) -> tuple[dict[str, Any], list[Section]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing front matter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    sections: list[Section] = []
    for line in body.splitlines():
        m = _HEADING.match(line)
        if m:
            tags = m.group("tags") or ""
            sections.append(Section(m.group("number"), m.group("title"), "[safety]" in tags, "[stop]" in tags))
        elif line.startswith("## "):
            raise ValueError(f"{path.name}: malformed heading {line!r}")
        elif sections:
            sections[-1].lines.append(line)
    if not sections:
        raise ValueError(f"{path.name}: no sections")
    return meta, sections


def _flowables(section: Section, styles: dict[str, ParagraphStyle]) -> list[Any]:
    out: list[Any] = [Paragraph(escape(f"{SECTION_MARK} {section.number} {section.title}"), styles["h"])]
    bullets: list[str] = []
    steps: list[str] = []
    table: list[list[str]] = []

    def flush() -> None:
        if bullets:
            out.append(
                ListFlowable([ListItem(Paragraph(escape(b), styles["b"])) for b in bullets], bulletType="bullet")
            )
            bullets.clear()
        if steps:
            items = [ListItem(Paragraph(escape(s), styles["b"])) for s in steps]
            out.append(ListFlowable(items, bulletType="1"))
            steps.clear()
        if table:
            t = Table(table, hAlign="LEFT")
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ]
                )
            )
            out.append(t)
            table.clear()

    for raw in section.lines:
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not all(set(c) <= {"-", ":"} for c in cells):
                table.append(cells)
        elif line.startswith("- "):
            bullets.append(line[2:])
        elif re.match(r"^\d+\.\s", line):
            steps.append(line.split(" ", 1)[1])
        else:
            flush()
            out.append(Paragraph(escape(line), styles["b"]))
    flush()
    out.append(Spacer(1, 4 * mm))
    return out


def _decorate(title: str):  # type: ignore[no-untyped-def]
    def on_page(canvas: Canvas, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.12))
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, WATERMARK)
        canvas.restoreState()
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(15 * mm, 10 * mm, f"{title} · {WATERMARK} · page {doc.page}")
        canvas.restoreState()

    return on_page


def render_pdf(meta: dict[str, Any], sections: list[Section], target: Path) -> None:
    base = getSampleStyleSheet()
    styles = {
        "t": ParagraphStyle("t", parent=base["Title"], fontSize=16),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontSize=12, spaceBefore=6),
        "b": ParagraphStyle("b", parent=base["BodyText"], fontSize=10, leading=13),
    }
    story: list[Any] = [Paragraph(escape(meta["title"]), styles["t"]), Paragraph(escape(WATERMARK), styles["b"])]
    for s in sections:
        story.extend(_flowables(s, styles))
    target.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(target), pagesize=A4, title=meta["title"], author="Veloxa Motors (SYNTHETIC)")
    deco = _decorate(meta["title"])
    doc.build(story, onFirstPage=deco, onLaterPages=deco)


def build(out: Path = OUT) -> dict[str, Any]:
    documents = []
    sources = sorted(SRC.glob("*.md")) + sorted((SRC / "tsb").glob("*.md")) + sorted((SRC / "recalls").glob("*.md"))
    for src in sources:
        meta, sections = parse_markdown(src)
        rel = Path(_SUBDIRS.get(meta["doc_type"], "")) / f"{meta['doc_id']}.pdf"
        render_pdf(meta, sections, out / rel)
        documents.append(
            {
                **meta,
                "source_file": rel.as_posix(),
                "sections": [
                    {
                        "section_id": f"{meta['doc_id']}#{s.number}",
                        "number": s.number,
                        "title": s.title,
                        "safety_critical": s.safety_critical,
                        "stop_required": s.stop_required,
                    }
                    for s in sections
                ],
            }
        )
    for csv_name in ("labour_time_guide.csv", "parts_price_list.csv"):
        shutil.copyfile(SRC / csv_name, out / csv_name)
    manifest = {"watermark": WATERMARK, "section_mark": SECTION_MARK, "documents": documents}
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    manifest = build()
    docs = manifest["documents"]
    by_type: dict[str, int] = {}
    for d in docs:
        by_type[d["doc_type"]] = by_type.get(d["doc_type"], 0) + 1
    sections = sum(len(d["sections"]) for d in docs)
    print(f"generate_knowledge: {len(docs)} PDFs, {sections} sections, by type {by_type} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
