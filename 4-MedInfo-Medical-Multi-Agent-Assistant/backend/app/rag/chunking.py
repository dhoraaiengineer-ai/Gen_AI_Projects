"""Chunking strategies.

- recursive:    RecursiveCharacterTextSplitter, 15% overlap
- semantic:     sentence-embedding breakpoints (needs an Embedder), 15% overlap between chunks
- parent_child: parents (15% overlap) are stored for context; small children (10% overlap) are embedded
- tables:       always table-aware: rows are never split and the header row is repeated in every chunk
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.interfaces import Embedder
from app.rag.loaders import Section
from app.safety.text import split_sentences

logger = logging.getLogger(__name__)

ChunkStrategy = Literal["recursive", "semantic", "parent_child"]
REGULAR_OVERLAP = 0.15
CHILD_OVERLAP = 0.10
_SEPARATORS = ["\n\n", "\n", ". ", "; ", ", ", " ", ""]


@dataclass(frozen=True)
class Chunk:
    text: str
    kind: Literal["text", "table", "child"]
    location: dict[str, Any]
    parent_id: str | None = None


@dataclass
class ChunkResult:
    chunks: list[Chunk]
    parents: dict[str, str] = field(default_factory=dict)


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _location(section: Section) -> dict[str, Any]:
    loc = {"page": section.page, "sheet": section.sheet, "slide": section.slide, "section": section.heading}
    loc = {k: v for k, v in loc.items() if v is not None}
    if section.ocr:
        loc["ocr"] = True
    if section.flagged:
        loc["injection_flagged"] = True
    return loc


def _splitter(size: int, overlap_ratio: float) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=int(size * overlap_ratio), separators=_SEPARATORS, keep_separator="end"
    )


def chunk_table(section: Section, max_chars: int) -> list[str]:
    """Group whole rows up to max_chars, repeating the header row at the top of every chunk."""
    lines = section.text.split("\n")
    header = section.header or lines[0]
    body = lines[1:] if lines and lines[0] == header else lines
    chunks: list[str] = []
    current: list[str] = []
    size = len(header)
    for row in body:
        if current and size + len(row) + 1 > max_chars:
            chunks.append("\n".join([header, *current]))
            current, size = [], len(header)
        current.append(row)
        size += len(row) + 1
    if current or not chunks:
        chunks.append("\n".join([header, *current]))
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _with_overlap(pieces: list[str], ratio: float) -> list[str]:
    """Prefix each piece with the tail (~ratio of its length) of the previous one, cut at a word boundary."""
    out: list[str] = []
    for i, piece in enumerate(pieces):
        if i == 0:
            out.append(piece)
            continue
        prev = pieces[i - 1]
        n = int(len(prev) * ratio)
        tail = prev[-n:] if n else ""
        if " " in tail:
            tail = tail[tail.index(" ") + 1 :]
        out.append(f"{tail} {piece}".strip() if tail else piece)
    return out


class Chunker:
    def __init__(
        self,
        strategy: ChunkStrategy = "recursive",
        *,
        chunk_size: int = 1000,
        parent_size: int = 2000,
        child_size: int = 400,
        embedder: Embedder | None = None,
        semantic_percentile: float = 90.0,
    ) -> None:
        if strategy == "semantic" and embedder is None:
            raise ValueError("semantic chunking needs an embedder")
        self.strategy = strategy
        self._chunk_size = chunk_size
        self._parent_size = parent_size
        self._child_size = child_size
        self._embedder = embedder
        self._percentile = semantic_percentile

    @property
    def config_signature(self) -> str:
        """Changes when chunking settings change, so re-chunked documents are re-indexed."""
        return json.dumps(
            [self.strategy, self._chunk_size, self._parent_size, self._child_size, self._percentile]
        )

    def chunk(self, doc_id: str, sections: list[Section]) -> ChunkResult:
        result = ChunkResult(chunks=[])
        for s_idx, section in enumerate(sections):
            loc = _location(section)
            if section.kind == "table":
                for text in chunk_table(section, self._chunk_size):
                    result.chunks.append(Chunk(text=text, kind="table", location=loc))
            elif self.strategy == "parent_child":
                self._parent_child(doc_id, s_idx, section, loc, result)
            elif self.strategy == "semantic":
                for text in self._semantic(section.text):
                    result.chunks.append(Chunk(text=text, kind="text", location=loc))
            else:
                for text in _splitter(self._chunk_size, REGULAR_OVERLAP).split_text(section.text):
                    result.chunks.append(Chunk(text=text.strip(), kind="text", location=loc))
        result.chunks = [c for c in result.chunks if c.text.strip()]
        logger.info(
            "chunked",
            extra={"strategy": self.strategy, "chunks": len(result.chunks), "parents": len(result.parents)},
        )
        return result

    def _parent_child(
        self, doc_id: str, s_idx: int, section: Section, loc: dict[str, Any], result: ChunkResult
    ) -> None:
        parents = _splitter(self._parent_size, REGULAR_OVERLAP).split_text(section.text)
        children_splitter = _splitter(self._child_size, CHILD_OVERLAP)
        for p_idx, parent in enumerate(parents):
            parent_id = "par_" + _hash(doc_id, str(s_idx), str(p_idx), parent)[:24]
            result.parents[parent_id] = parent.strip()
            for child in children_splitter.split_text(parent):
                result.chunks.append(
                    Chunk(text=child.strip(), kind="child", location=loc, parent_id=parent_id)
                )

    def _semantic(self, text: str) -> list[str]:
        sentences = split_sentences(text)
        if len(sentences) <= 2:
            return [text.strip()]
        assert self._embedder is not None
        vectors = self._embedder.embed_documents(sentences)
        distances = [1 - _cosine(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        ranked = sorted(distances)
        threshold = ranked[min(len(ranked) - 1, int(len(ranked) * self._percentile / 100))]
        groups: list[list[str]] = [[sentences[0]]]
        for sentence, dist in zip(sentences[1:], distances, strict=True):
            size = sum(len(s) for s in groups[-1])
            if dist >= threshold or size + len(sentence) > self._chunk_size:
                groups.append([sentence])
            else:
                groups[-1].append(sentence)
        pieces = [" ".join(g) for g in groups]
        # Oversized single sentences still respect the size limit.
        splitter = _splitter(self._chunk_size, 0.0)
        sized = [part for piece in pieces for part in (splitter.split_text(piece) or [piece])]
        return _with_overlap(sized, REGULAR_OVERLAP)


def chunk_content_hash(chunk: Chunk, provenance_sig: str, chunker_sig: str) -> str:
    """Hash of everything that ends up in the index row; unchanged hash means no re-embedding."""
    return _hash(
        chunk.text, chunk.kind, json.dumps(chunk.location, sort_keys=True), provenance_sig, chunker_sig
    )


def chunk_ids(doc_id: str, hashes: list[str]) -> list[str]:
    """Position-independent ids: same content -> same id, so inserting a paragraph doesn't re-embed the rest."""
    seen: dict[str, int] = {}
    ids = []
    for h in hashes:
        n = seen.get(h, 0)
        seen[h] = n + 1
        ids.append(str(uuid.UUID(hex=_hash(doc_id, h, str(n))[:32])))
    return ids
