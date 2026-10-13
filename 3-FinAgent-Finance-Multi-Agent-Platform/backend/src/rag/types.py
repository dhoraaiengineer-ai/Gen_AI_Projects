"""RAG data types and ports (SDK-free)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol

SectionKind = Literal["text", "table", "record", "code", "slide", "image"]
TokenCounter = Callable[[str], int]


@dataclass
class Section:
    """A loader's unit of content with its location (page, sheet, slide, heading path ...)."""

    text: str
    kind: SectionKind = "text"
    location: dict[str, Any] = field(default_factory=dict)
    heading_path: list[str] = field(default_factory=list)
    table: list[list[str]] | None = None  # header row first, for kind="table"


@dataclass
class LoadedDocument:
    source: str
    source_type: (
        str  # pdf | docx | xlsx | csv | pptx | md | txt | json | xml | html | sql | eml | image
    )
    title: str
    sections: list[Section]
    page_count: int | None = None
    needs_ocr: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentMeta:
    doc_type: str  # filing | statement | research | news | policy | regulation | internal ...
    classification: str = "internal"
    ticker: str | None = None
    fiscal_period: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    title: str | None = None


@dataclass
class Chunk:
    id: str
    ordinal: int
    strategy: str
    content: str
    level: str = "leaf"  # leaf | parent | child | summary | section
    parent_id: str | None = None
    context_header: str = ""
    location: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    embed: bool = True  # parents are stored for context but not embedded

    @property
    def embed_text(self) -> str:
        return f"{self.context_header}\n{self.content}" if self.context_header else self.content


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    source: str
    title: str
    content: str
    context: str  # what the answer sees (parent section / sentence window / the chunk)
    location: dict[str, Any]
    doc_type: str
    ticker: str | None
    fiscal_period: str | None
    classification: str
    ingested_at: str
    content_hash: str
    vector_rank: int | None = None
    text_rank: int | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    parent_id: str | None = None

    @property
    def relevance_score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.fused_score

    def citation(self) -> str:
        loc = self.location
        if "page" in loc:
            where = f"p. {loc['page']}" + (" (OCR)" if loc.get("ocr") else "")
        elif "sheet" in loc:
            rows = f", rows {loc['rows']}" if loc.get("rows") else ""
            where = f"sheet {loc['sheet']}{rows}"
        elif "slide" in loc:
            where = f"slide {loc['slide']}"
        elif "section" in loc:
            where = f'section "{loc["section"]}"'
        elif "rows" in loc:
            where = f"rows {loc['rows']}"
        elif "statement" in loc:
            where = f"statement {loc['statement']}"
        elif "path" in loc:
            where = str(loc["path"])
        else:
            where = ""
        return f"{self.source}, {where}" if where else self.source


class Ocr(Protocol):
    """OCR port (implemented in ``src/providers/ocr.py``)."""

    def available(self) -> bool: ...

    def image_text(self, data: bytes) -> str: ...

    def pdf_page_text(self, data: bytes, page_index: int) -> str: ...


class Reranker(Protocol):
    name: str

    async def scores(self, query: str, passages: Sequence[str]) -> list[float]: ...
