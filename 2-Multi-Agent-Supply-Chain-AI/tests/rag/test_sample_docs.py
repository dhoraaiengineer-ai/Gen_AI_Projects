"""Loaders parse every sample format, and every golden evidence quote appears verbatim in its source document."""

import json
from pathlib import Path

import pytest

from app.rag import chunking, loaders

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "data" / "sample_docs"
GOLDEN = ROOT / "evals" / "golden" / "rag_golden.json"

pytestmark = pytest.mark.skipif(not DOCS.exists(), reason="run scripts/generate_sample_docs.py first")


def _text(name: str) -> str:
    sections = loaders.load(name, (DOCS / name).read_bytes(), ocr=None)
    return "\n".join(s.text for s in sections)


def test_every_golden_evidence_quote_is_verbatim_in_its_document() -> None:
    for item in json.loads(GOLDEN.read_text(encoding="utf-8")):
        if item.get("expect_refusal"):
            continue
        text = " ".join(_text(item["source"]).split())
        assert " ".join(item["evidence"].split()) in text, f"{item['source']}: {item['evidence']!r}"


def test_pdf_has_one_section_per_page_with_page_locations() -> None:
    sections = loaders.load("Global Procurement Policy v4.2.pdf", (DOCS / "Global Procurement Policy v4.2.pdf").read_bytes())
    assert [s.location for s in sections] == ["p. 1", "p. 2", "p. 3", "p. 4"]


def test_xlsx_sheets_become_tables_and_chunk_with_repeated_header() -> None:
    sections = loaders.load("Carrier Rate Card Q4.xlsx", (DOCS / "Carrier Rate Card Q4.xlsx").read_bytes())
    assert {s.location for s in sections} == {"sheet Rates", "sheet Notes"}
    chunks = chunking.table(sections, size=120)
    rates = [c for c in chunks if c.location == "sheet Rates"]
    assert len(rates) > 1
    assert all(c.text.startswith("| Lane |") for c in rates)


def test_pptx_slides_include_tables_and_notes() -> None:
    sections = loaders.load("International Shipping Policy.pptx", (DOCS / "International Shipping Policy.pptx").read_bytes())
    assert sections[0].location == "slide 1"
    joined = "\n".join(s.text for s in sections)
    assert "Speaker notes:" in joined and "| Critical stockout | Air |" in joined


def test_docx_keeps_headings_paragraphs_and_tables_in_order() -> None:
    text = _text("Nordvolt Energy - Master Supply Agreement.docx")
    assert text.index("## Terms") < text.index("Clause 6.1") < text.index("| Supplier ID |")


def test_image_without_ocr_is_rejected_clearly() -> None:
    with pytest.raises(loaders.UnsupportedDocument, match="OCR"):
        loaders.load("scan.png", (DOCS / "Freight Invoice FI-20914 (scan).png").read_bytes(), ocr=None)


def test_legacy_formats_rejected() -> None:
    with pytest.raises(loaders.UnsupportedDocument, match=r"\.xlsx"):
        loaders.load("old.xls", b"\xd0\xcf")


def test_crlf_normalised() -> None:
    assert loaders.normalise("a\r\nb\r\n\r\n\r\nc") == "a\nb\n\nc"
