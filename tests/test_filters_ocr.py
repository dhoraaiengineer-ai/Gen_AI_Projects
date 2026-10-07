"""Metadata filtering and OCR."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.rag import loaders, ocr
from app.rag.filters import MetadataFilter, to_pgvector_filter
from app.rag.loaders import UnsupportedFileError, load_file
from app.rag.retriever import Retriever
from tests.conftest import AppHarness

# ---------- metadata filters ----------


def test_filter_build_normalizes_and_drops_empty() -> None:
    assert MetadataFilter.build() is None
    f = MetadataFilter.build(file_types=[".PDF"], tags=[" Finance ", "finance"])
    assert f == MetadataFilter((), ("pdf",), ("finance",))


def test_filter_matches_on_source_type_and_tags() -> None:
    f = MetadataFilter(sources=("a.pdf", "b.xlsx"), file_types=("pdf",), tags=("finance",))
    assert f.matches({"source": "a.pdf", "tags": ",finance,2024,"})
    assert not f.matches({"source": "b.xlsx", "tags": ",finance,"})  # wrong type
    assert not f.matches({"source": "a.pdf", "tags": ",fin,"})  # tags match whole words only
    assert MetadataFilter(file_types=("pdf",)).matches({"source": "old-upload.PDF"})  # works without file_type


def test_pgvector_filter_translation() -> None:
    assert to_pgvector_filter(MetadataFilter(sources=("a.pdf",))) == {"source": {"$in": ["a.pdf"]}}
    both = to_pgvector_filter(MetadataFilter(file_types=("pdf", "xlsx"), tags=("hr",)))
    assert both == {
        "$and": [
            {"$or": [{"source": {"$ilike": "%.pdf"}}, {"source": {"$ilike": "%.xlsx"}}]},
            {"tags": {"$ilike": "%,hr,%"}},
        ]
    }


def test_retrieval_respects_filters(retriever: Retriever) -> None:
    retriever.ingest_text("Revenue grew in March.", source="report.pdf")
    retriever.ingest_text("Revenue fell in April.", source="sales.xlsx")
    hits = retriever.retrieve("revenue", k=4, filters=MetadataFilter(file_types=("xlsx",)))
    assert [h.source for h in hits] == ["sales.xlsx"]


def test_api_filters_tags_and_cache_scope(harness: AppHarness) -> None:
    docs = {
        "documents": [
            {"text": "Leave policy: 20 days.", "source": "hr.md"},
            {"text": "Leave the office by 6 pm.", "source": "ops.md"},
        ],
        "tags": ["HR"],
    }
    with harness.client("From HR [1].", "Everything [1].", "Tagged [1].") as c:
        c.post("/api/v1/ingest", json=docs)
        scoped = c.post("/api/v1/query", json={"question": "leave", "filters": {"sources": ["hr.md"]}}).json()
        unscoped = c.post("/api/v1/query", json={"question": "leave"}).json()
        tagged = c.post("/api/v1/query", json={"question": "leave", "filters": {"tags": ["hr"]}}).json()
        sources = c.get("/api/v1/sources").json()

    assert [s["source"] for s in scoped["sources"]] == ["hr.md"]
    assert unscoped["cached"] is False  # a filtered answer is never served for an unfiltered question
    assert len(tagged["sources"]) == 2  # both documents were uploaded with tag "hr"
    assert {s["source"]: s["file_type"] for s in sources["sources"]} == {"hr.md": "md", "ops.md": "md"}


def test_sources_endpoint_is_for_signed_in_users(harness: AppHarness) -> None:
    with harness.client(role=None) as c:
        assert c.get("/api/v1/sources").status_code == 401


# ---------- OCR ----------


class FakeOcr:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def read(self, image: bytes) -> str:
        self.calls += 1
        return self.text


@pytest.fixture
def fake_ocr():  # type: ignore[no-untyped-def]
    engine = FakeOcr("ISSN 2799-0417\nVolume 14")
    ocr.set_default_engine(engine)
    yield engine
    ocr.set_default_engine(None)


def _image(text: str = "Scanned page", fmt: str = "PNG") -> bytes:
    img = Image.new("RGB", (900, 160), "white")
    ImageDraw.Draw(img).text((20, 40), text, fill="black", font=ImageFont.load_default(size=48))
    buffer = io.BytesIO()
    img.save(buffer, fmt)
    return buffer.getvalue()


def test_image_upload_is_read_with_ocr(fake_ocr: FakeOcr) -> None:
    [section] = load_file("scan.PNG", _image()).sections
    assert section.text == "ISSN 2799-0417\nVolume 14"
    assert section.metadata == {"ocr": "true"}


def test_scanned_pdf_pages_fall_back_to_ocr(fake_ocr: FakeOcr) -> None:
    pdf = _image(fmt="PDF")  # an image-only PDF: no text layer, like a scan
    [section] = load_file("scan.pdf", pdf).sections
    assert section.metadata == {"page": "1", "ocr": "true"}
    assert fake_ocr.calls == 1


def test_ocr_can_be_disabled(fake_ocr: FakeOcr, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loaders, "OCR_ENABLED", False)
    with pytest.raises(UnsupportedFileError, match="OCR"):
        load_file("scan.png", _image())


def test_blank_image_is_rejected() -> None:
    ocr.set_default_engine(FakeOcr(""))
    try:
        with pytest.raises(UnsupportedFileError, match="no text"):
            load_file("blank.jpg", _image("", "JPEG"))
    finally:
        ocr.set_default_engine(None)


def test_real_ocr_reads_rendered_text() -> None:
    """End-to-end with the bundled RapidOCR models (offline; the first model load takes a few seconds)."""
    pytest.importorskip("rapidocr_onnxruntime")
    ocr.set_default_engine(None)
    text = ocr.default_engine().read(_image("Journal ISSN 2799-0417"))
    assert "2799-0417" in text
