"""Chunking strategies (docs/rag-architecture.md).

fixed · sliding_window · recursive · sentence_window · semantic · structure · parent_child ·
hierarchical · table · record · code · slide · multimodal · proposition — plus ``auto``, which picks
per section. Sizes are tokens. Every chunk keeps its location and gets a contextual header
(title › type › ticker period › section path) that is embedded and indexed with it. Chunk ids are
deterministic: sha256(document_id, strategy, location, ordinal).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.core.errors import ValidationFailed
from src.core.tokens import estimate_tokens
from src.rag.loaders import table_markdown
from src.rag.types import Chunk, DocumentMeta, LoadedDocument, Section, TokenCounter

STRATEGIES = (
    "auto",
    "fixed",
    "sliding_window",
    "recursive",
    "sentence_window",
    "semantic",
    "structure",
    "parent_child",
    "hierarchical",
    "table",
    "record",
    "code",
    "slide",
    "multimodal",
    "proposition",
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
SimilarityFn = Callable[[Sequence[str]], Sequence[float]]  # adjacent-sentence cosine similarity
PropositionFn = Callable[[str], list[str]]


@dataclass
class ChunkingConfig:
    fixed_size: int = 400
    fixed_overlap: float = 0.15
    window_size: int = 300
    window_overlap: float = 0.5
    recursive_size: int = 800
    recursive_overlap: float = 0.15
    sentence_k: int = 3
    semantic_min: int = 200
    semantic_max: int = 1200
    semantic_percentile: float = 95.0
    structure_max: int = 1200
    parent_size: int = 2000
    child_size: int = 400
    child_overlap: float = 0.10
    summary_max: int = 300
    table_rows_tokens: int = 400
    record_merge_below: int = 40
    record_max: int = 200
    parent_child_threshold: int = 4000
    by_doc_type: dict[str, str] = field(default_factory=dict)  # doc_type → forced strategy


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.replace("\n", " ")) if s.strip()]


class _Builder:
    def __init__(
        self, doc: LoadedDocument, meta: DocumentMeta, document_id: str, count: TokenCounter
    ) -> None:
        self.doc, self.meta, self.document_id, self.count = doc, meta, document_id, count
        self.chunks: list[Chunk] = []

    def header(self, section: Section | None) -> str:
        parts = [self.meta.title or self.doc.title, self.meta.doc_type]
        tag = " ".join(p for p in (self.meta.ticker, self.meta.fiscal_period) if p)
        if tag:
            parts.append(tag)
        if section and section.heading_path:
            parts.append(" › ".join(section.heading_path))
        return " › ".join(p for p in parts if p)[:480]

    def add(
        self,
        content: str,
        strategy: str,
        section: Section | None,
        *,
        level: str = "leaf",
        parent: Chunk | None = None,
        embed: bool = True,
        extra_location: dict[str, Any] | None = None,
    ) -> Chunk:
        location = {**(section.location if section else {}), **(extra_location or {})}
        ordinal = len(self.chunks)
        key = json.dumps(
            [self.document_id, strategy, location, ordinal], sort_keys=True, default=str
        )
        chunk = Chunk(
            id=hashlib.sha256(key.encode("utf-8")).hexdigest(),
            ordinal=ordinal,
            strategy=strategy,
            content=content.strip(),
            level=level,
            parent_id=parent.id if parent else None,
            context_header=self.header(section),
            location=location,
            token_count=self.count(content),
            embed=embed,
        )
        self.chunks.append(chunk)
        return chunk


# ------------------------------------------------------------------------- text splitters
def token_windows(text: str, size: int, overlap: float, count: TokenCounter) -> list[str]:
    words = text.split()
    if not words:
        return []
    costs = [max(count(w + " "), 1) for w in words]
    step_tokens = max(int(size * (1 - overlap)), 1)
    out: list[str] = []
    start = 0
    while start < len(words):
        total, end = 0, start
        while end < len(words) and total + costs[end] <= size:
            total += costs[end]
            end += 1
        end = max(end, start + 1)
        out.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        advanced, nxt = 0, start
        while nxt < end and advanced < step_tokens:
            advanced += costs[nxt]
            nxt += 1
        start = max(nxt, start + 1)
    return out


def recursive_split(
    text: str,
    size: int,
    overlap: float,
    count: TokenCounter,
    separators: Sequence[str] = ("\n\n", "\n", ". ", " "),
) -> list[str]:
    """Split on the coarsest separator that works, then merge neighbours up to ``size``."""
    if count(text) <= size:
        return [text] if text.strip() else []
    sep = next((s for s in separators if s in text), None)
    if sep is None:
        return token_windows(text, size, overlap, count)
    rest = separators[separators.index(sep) + 1 :]
    pieces: list[str] = []
    for part in text.split(sep):
        if not part.strip():
            continue
        piece = part + (sep if sep == ". " else "")
        pieces += (
            recursive_split(piece, size, overlap, count, rest) if count(piece) > size else [piece]
        )
    merged: list[str] = []
    current: list[str] = []
    joiner = "" if sep == ". " else sep
    for piece in pieces:
        candidate = joiner.join([*current, piece])
        if current and count(candidate) > size:
            merged.append(joiner.join(current))
            keep: list[str] = []
            budget = int(size * overlap)
            for prev in reversed(current):  # overlap: carry trailing pieces forward
                if count(joiner.join([prev, *keep])) > budget:
                    break
                keep.insert(0, prev)
            current = [*keep, piece]
        else:
            current.append(piece)
    if current:
        merged.append(joiner.join(current))
    return [m.strip() for m in merged if m.strip()]


# ------------------------------------------------------------------------------ strategies
def _fixed(b: _Builder, s: Section, cfg: ChunkingConfig) -> None:
    for text in token_windows(s.text, cfg.fixed_size, cfg.fixed_overlap, b.count):
        b.add(text, "fixed", s)


def _sliding(b: _Builder, s: Section, cfg: ChunkingConfig) -> None:
    for text in token_windows(s.text, cfg.window_size, cfg.window_overlap, b.count):
        b.add(text, "sliding_window", s)


def _recursive(b: _Builder, s: Section, cfg: ChunkingConfig) -> None:
    for text in recursive_split(s.text, cfg.recursive_size, cfg.recursive_overlap, b.count):
        b.add(text, "recursive", s)


def _sentence_window(b: _Builder, s: Section, cfg: ChunkingConfig) -> None:
    sentences = split_sentences(s.text)
    for i, sentence in enumerate(sentences):
        window = " ".join(sentences[max(0, i - cfg.sentence_k) : i + cfg.sentence_k + 1])
        b.add(sentence, "sentence_window", s, extra_location={"sentence": i + 1, "context": window})


def semantic_breaks(similarities: Sequence[float], percentile: float) -> set[int]:
    """Indices *after which* to break: adjacent-sentence distance above the percentile."""
    if not similarities:
        return set()
    distances = 1 - np.asarray(similarities, dtype=np.float64)
    cut = float(np.percentile(distances, percentile))
    return {i for i, d in enumerate(distances) if d >= cut and d > 0}


def _semantic(
    b: _Builder, s: Section, cfg: ChunkingConfig, similarity: SimilarityFn | None
) -> None:
    if similarity is None:
        raise ValidationFailed("semantic chunking needs an embedding model")
    sentences = split_sentences(s.text)
    if len(sentences) < 3:
        b.add(s.text, "semantic", s)
        return
    breaks = semantic_breaks(similarity(sentences), cfg.semantic_percentile)
    current: list[str] = []
    for i, sentence in enumerate(sentences):
        current.append(sentence)
        size = b.count(" ".join(current))
        if size >= cfg.semantic_max or (i in breaks and size >= cfg.semantic_min):
            b.add(" ".join(current), "semantic", s)
            current = []
    if current:
        b.add(" ".join(current), "semantic", s)


def _structure(b: _Builder, s: Section, cfg: ChunkingConfig) -> None:
    if b.count(s.text) <= cfg.structure_max:
        b.add(s.text, "structure", s)
        return
    for text in recursive_split(s.text, cfg.structure_max, cfg.recursive_overlap, b.count):
        b.add(text, "structure", s)


def _parent_child(b: _Builder, sections: Sequence[Section], cfg: ChunkingConfig) -> None:
    for s in sections:
        for parent_text in recursive_split(s.text, cfg.parent_size, 0.0, b.count):
            parent = b.add(parent_text, "parent_child", s, level="parent", embed=False)
            for child in recursive_split(parent_text, cfg.child_size, cfg.child_overlap, b.count):
                b.add(child, "parent_child", s, level="child", parent=parent)


def _hierarchical(b: _Builder, sections: Sequence[Section], cfg: ChunkingConfig) -> None:
    leads = []
    for s in sections:
        first = split_sentences(s.text)[:1]
        label = " › ".join(s.heading_path)
        if first:
            leads.append(f"{label}: {first[0]}" if label else first[0])
    summary_text = " ".join(token_windows(" ".join(leads), cfg.summary_max, 0.0, b.count)[:1])
    summary = b.add(
        f"Summary of {b.meta.title or b.doc.title}: {summary_text}",
        "hierarchical",
        None,
        level="summary",
        extra_location={"level": "document"},
    )
    for s in sections:
        sec = b.add(
            " ".join(token_windows(s.text, cfg.structure_max, 0.0, b.count)[:1]),
            "hierarchical",
            s,
            level="section",
            parent=summary,
        )
        for para in recursive_split(s.text, cfg.child_size, cfg.child_overlap, b.count):
            b.add(para, "hierarchical", s, level="leaf", parent=sec)


def _table(b: _Builder, s: Section, cfg: ChunkingConfig) -> None:
    rows = s.table or [r.split(" | ") for r in s.text.split("\n")]
    if not rows:
        return
    header, body = rows[0], rows[1:] or []
    where = ", ".join(f"{k} {v}" for k, v in s.location.items()) or b.doc.source
    group: list[list[str]] = []
    start = 1

    def emit(end: int) -> None:
        caption = (
            f"Table from {b.doc.source} ({where}); columns: {', '.join(header)}; "
            f"rows {start}-{end}."
        )
        b.add(
            f"{caption}\n{table_markdown([header, *group])}",
            "table",
            s,
            extra_location={"rows": f"{start}-{end}"},
        )

    header_cost = b.count(table_markdown([header]))
    for i, row in enumerate(body, start=1):
        group.append(row)
        if (
            header_cost + b.count(table_markdown([header, *group])) > cfg.table_rows_tokens
            and len(group) > 1
        ):
            group.pop()
            emit(i - 1)
            group, start = [row], i
    if group or not body:
        emit(start + len(group) - 1 if group else 0)


def _records(b: _Builder, sections: Sequence[Section], cfg: ChunkingConfig) -> None:
    pending: list[Section] = []

    def flush() -> None:
        if not pending:
            return
        paths = [str(p.location.get("path", i)) for i, p in enumerate(pending)]
        loc = {"path": paths[0] if len(paths) == 1 else f"{paths[0]} … {paths[-1]}"}
        b.add("\n\n".join(p.text for p in pending), "record", pending[0], extra_location=loc)
        pending.clear()

    for s in sections:
        size = b.count(s.text)
        merged = sum(b.count(p.text) for p in pending) + size
        if pending and (size >= cfg.record_merge_below or merged > cfg.record_max):
            flush()
        pending.append(s)
        if size >= cfg.record_merge_below:
            flush()
    flush()


def _multimodal(b: _Builder, s: Section, captioner: Callable[[Section], str] | None) -> None:
    caption = captioner(s) if captioner else ""
    text = f"Figure (OCR text): {s.text}" + (f"\nCaption: {caption}" if caption else "")
    b.add(text, "multimodal", s)


def _proposition(b: _Builder, s: Section, propose: PropositionFn | None) -> None:
    if propose is None:
        raise ValidationFailed("proposition chunking is opt-in and needs an LLM")
    for statement in propose(s.text):
        if statement.strip():
            b.add(statement, "proposition", s)


def choose_strategy(doc: LoadedDocument, meta: DocumentMeta, section: Section, total: int) -> str:
    kind_map = {
        "table": "table",
        "record": "record",
        "code": "code",
        "slide": "slide",
        "image": "multimodal",
    }
    if section.kind in kind_map:
        return kind_map[section.kind]
    if any(s.heading_path for s in doc.sections):
        return "parent_child" if total > 4000 else "structure"
    return "recursive" if meta.doc_type in {"filing", "research", "statement"} else "fixed"


def chunk_document(  # noqa: PLR0912 — one branch per strategy family
    doc: LoadedDocument,
    meta: DocumentMeta,
    document_id: str,
    *,
    strategy: str = "auto",
    config: ChunkingConfig | None = None,
    count: TokenCounter = estimate_tokens,
    similarity: SimilarityFn | None = None,
    propose: PropositionFn | None = None,
    captioner: Callable[[Section], str] | None = None,
) -> list[Chunk]:
    if strategy not in STRATEGIES:
        raise ValidationFailed(f"unknown chunking strategy {strategy!r}")
    cfg = config or ChunkingConfig()
    strategy = cfg.by_doc_type.get(meta.doc_type, strategy) if strategy == "auto" else strategy
    b = _Builder(doc, meta, document_id, count)
    sections = [s for s in doc.sections if s.text.strip()]
    total = sum(count(s.text) for s in sections)
    text_like = {"text", "slide", "code", "record", "image"}

    if strategy == "hierarchical":
        _hierarchical(b, sections, cfg)
        return b.chunks
    if strategy == "parent_child":
        _parent_child(b, [s for s in sections if s.kind in text_like], cfg)
        for s in sections:
            if s.kind == "table":
                _table(b, s, cfg)
        return b.chunks

    groups: dict[str, list[Section]] = {}
    order: list[tuple[str, Section]] = []
    for s in sections:
        chosen = choose_strategy(doc, meta, s, total) if strategy == "auto" else strategy
        if s.kind == "table" and chosen not in {"table"}:
            chosen = "table" if strategy == "auto" else chosen
        order.append((chosen, s))
        groups.setdefault(chosen, []).append(s)

    if "parent_child" in groups:
        _parent_child(b, groups.pop("parent_child"), cfg)
    if "record" in groups:
        _records(b, groups.pop("record"), cfg)
    simple: dict[str, Callable[[_Builder, Section, ChunkingConfig], None]] = {
        "fixed": _fixed,
        "sliding_window": _sliding,
        "recursive": _recursive,
        "sentence_window": _sentence_window,
        "structure": _structure,
        "table": _table,
    }
    for chosen, s in order:
        if chosen not in groups:
            continue
        if chosen in simple:
            simple[chosen](b, s, cfg)
        elif chosen in {"code", "slide"}:
            b.add(s.text, chosen, s)
        elif chosen == "multimodal":
            _multimodal(b, s, captioner)
        elif chosen == "semantic":
            _semantic(b, s, cfg, similarity)
        elif chosen == "proposition":
            _proposition(b, s, propose)
    return b.chunks
