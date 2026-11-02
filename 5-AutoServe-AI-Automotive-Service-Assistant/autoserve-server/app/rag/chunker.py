"""Structure-aware chunking of corpus PDFs (rules/50).

Each `§ <number> <title>` heading starts a unit (procedure, spec table, warning-light entry, TSB, recall, DTC entry)
that is kept whole. Units longer than `max_chars` are split with overlap. Watermark/footer lines are removed.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader

SECTION_MARK = "§"
WATERMARK = "SYNTHETIC — FOR DEMO ONLY"
_FOOTER = re.compile(rf"^.*·\s*{re.escape(WATERMARK)}\s*·\s*page\s+\d+\s*$")


@dataclass
class RawSection:
    number: str
    title: str
    page: int
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        body = "\n".join(self.lines).strip()
        return f"{SECTION_MARK} {self.number} {self.title}\n{body}".strip()


@dataclass(frozen=True)
class Chunk:
    section_id: str
    section_title: str
    page: int
    content: str
    content_hash: str
    metadata: dict[str, Any]


def pdf_pages(pdf_bytes: bytes) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages]


def split_sections(pages: list[str]) -> list[RawSection]:
    sections: list[RawSection] = []
    for page_no, text in enumerate(pages, start=1):
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line == WATERMARK or _FOOTER.match(line):
                continue
            line = line.replace(WATERMARK, "").strip()
            if not line:
                continue
            if line.startswith(SECTION_MARK + " "):
                head = line[len(SECTION_MARK) + 1 :].strip()
                number, _, title = head.partition(" ")
                sections.append(RawSection(number=number, title=title.strip(), page=page_no))
            elif sections:
                sections[-1].lines.append(line)
    return sections


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            cut = text.rfind("\n", start + max_chars // 2, end)
            end = cut if cut > start else end
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return parts


def content_hash(doc_id: str, section_id: str, content: str) -> str:
    return hashlib.sha256(f"{doc_id}\x1f{section_id}\x1f{content}".encode()).hexdigest()


def build_chunks(
    pdf_bytes: bytes,
    doc: dict[str, Any],
    *,
    max_chars: int,
    overlap: int,
) -> list[Chunk]:
    """`doc` is a manifest document entry (or an admin-upload equivalent without per-section flags)."""
    flags = {s["number"]: s for s in doc.get("sections", [])}
    model = None if str(doc.get("model", "")).lower() in ("", "all") else doc["model"]
    vin_range = (
        f"{doc['vin_serial_from']}-{doc['vin_serial_to']}"
        if doc.get("vin_serial_from") and doc.get("vin_serial_to")
        else None
    )
    chunks: list[Chunk] = []
    for raw in split_sections(pdf_pages(pdf_bytes)):
        section_id = f"{doc['doc_id']}#{raw.number}"
        flag = flags.get(raw.number, {})
        base_meta: dict[str, Any] = {
            "doc_id": doc["doc_id"],
            "doc_type": doc["doc_type"],
            "model": model,
            "model_year_from": doc.get("model_year_from"),
            "model_year_to": doc.get("model_year_to"),
            "vin_range": vin_range,
            "section_id": section_id,
            "section_title": raw.title,
            "page": raw.page,
            "source_file": doc["source_file"],
            "version": str(doc.get("version", "")),
            "visibility": doc["visibility"],
            "safety_critical": bool(flag.get("safety_critical", False)),
            "stop_required": bool(flag.get("stop_required", False)),
        }
        for key in ("dtcs", "op_code", "campaign_code", "symptom_keywords"):
            if key in doc:
                base_meta[key] = doc[key]
        parts = _split_long(raw.text, max_chars, overlap)
        for i, part in enumerate(parts):
            sid = section_id if len(parts) == 1 else f"{section_id}~{i + 1}"
            chunks.append(
                Chunk(
                    section_id=sid,
                    section_title=raw.title,
                    page=raw.page,
                    content=part,
                    content_hash=content_hash(doc["doc_id"], sid, part),
                    metadata={**base_meta, "section_id": sid, "part": i + 1, "parts": len(parts)},
                )
            )
    return chunks
