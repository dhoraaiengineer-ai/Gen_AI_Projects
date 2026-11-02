"""Large uploaded documents (>10k chars) are extracted in page windows and merged deterministically."""

from __future__ import annotations

from app.documents.extract import WINDOW_CHARS, llm_extract, merge_extractions, page_windows
from app.documents.ocr import PageText
from app.documents.schemas.extraction import DocExtraction, F, LineItem
from app.services.llm_service import FakeLLM


def pages(n: int, chars: int) -> list[PageText]:
    return [PageText(i, "x" * chars, "pdf_text") for i in range(1, n + 1)]


def test_small_document_is_one_window() -> None:
    assert len(page_windows(pages(3, 1000))) == 1


def test_large_document_is_split_on_page_boundaries_within_budget() -> None:
    windows = page_windows(pages(12, 3000))  # 36k chars
    assert len(windows) > 1
    assert all(sum(len(p.text) for p in w) <= WINDOW_CHARS for w in windows)
    assert [p.page for w in windows for p in w] == list(range(1, 13))  # every page once, in order


def test_single_oversized_page_is_split_without_losing_text() -> None:
    text = "y" * (WINDOW_CHARS * 2 + 5)
    windows = page_windows([PageText(1, text, "pdf_text")])
    assert len(windows) == 3 and all(p.page == 1 for w in windows for p in w)
    assert "".join(p.text for w in windows for p in w) == text


def test_merge_keeps_highest_confidence_and_concatenates_lines() -> None:
    a = DocExtraction(vin=F(value="VIN-A", confidence=0.6, source_page=1), lines=[LineItem(part_number=F(value="P1"))])
    b = DocExtraction(
        vin=F(value="VIN-B", confidence=0.9, source_page=5),
        total=F(value="100.00", confidence=0.8),
        lines=[LineItem(part_number=F(value="P2"))],
    )
    m = merge_extractions([a, b])
    assert m.vin.value == "VIN-B" and m.vin.source_page == 5
    assert m.total.value == "100.00"
    assert [line.part_number.value for line in m.lines] == ["P1", "P2"]


async def test_llm_extract_calls_once_per_window() -> None:
    big = pages(10, 3000)
    n = len(page_windows(big))
    fake = FakeLLM(structured=[{"vin": {"value": "V", "confidence": 0.9, "source_page": 1}}] * n)
    await llm_extract(big, "parts_invoice", fake, None)
    assert len(fake.calls) == n
    assert all("part " in str(c[2][1].content) for c in fake.calls)
