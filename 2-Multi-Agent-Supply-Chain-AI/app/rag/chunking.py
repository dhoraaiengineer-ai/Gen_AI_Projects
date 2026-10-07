"""Chunking strategies, selectable per upload. Overlap is a percentage of chunk size.

| Strategy     | Behaviour                                                                    |
|--------------|------------------------------------------------------------------------------|
| recursive    | default; paragraph → sentence → word boundaries, 15% overlap                 |
| semantic     | breaks where neighbouring-sentence embedding distance exceeds a percentile   |
| parent_child | embeds small children (10% overlap), returns the larger parent once          |
| table        | splits only between rows and repeats the header; default for sheets/CSV      |
"""

from __future__ import annotations

import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loaders import Section

Strategy = Literal["recursive", "semantic", "parent_child", "table"]

CHUNK_SIZE = 1000
PARENT_SIZE = 2000
CHILD_SIZE = 400
DEFAULT_OVERLAP_PCT = 15
CHILD_OVERLAP_PCT = 10
SEMANTIC_PERCENTILE = 90


@dataclass
class Chunk:
    text: str
    location: str
    ocr: bool = False
    parent_key: str | None = None  # parent_child: children reference their parent's text key
    is_parent: bool = False


def _splitter(size: int, overlap_pct: float) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=int(size * overlap_pct / 100), separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""]
    )


def recursive(sections: list[Section], overlap_pct: float = DEFAULT_OVERLAP_PCT, size: int = CHUNK_SIZE) -> list[Chunk]:
    splitter = _splitter(size, overlap_pct)
    return [Chunk(t, s.location, s.ocr) for s in sections for t in splitter.split_text(s.text) if t.strip()]


def table(sections: list[Section], size: int = CHUNK_SIZE) -> list[Chunk]:
    """Split markdown tables between rows only, repeating the header in every chunk."""
    chunks: list[Chunk] = []
    for s in sections:
        lines = s.text.split("\n")
        if not (s.is_table or (len(lines) > 2 and lines[0].startswith("|") and set(lines[1]) <= set("|-: "))):
            chunks += recursive([s], size=size)
            continue
        header, rows = lines[:2], lines[2:]
        current: list[str] = []
        for row in rows:
            if current and len("\n".join(header + current + [row])) > size:
                chunks.append(Chunk("\n".join(header + current), s.location, s.ocr))
                current = []
            current.append(row)
        if current:
            chunks.append(Chunk("\n".join(header + current), s.location, s.ocr))
    return chunks


def parent_child(sections: list[Section], overlap_pct: float = CHILD_OVERLAP_PCT) -> list[Chunk]:
    parent_splitter = _splitter(PARENT_SIZE, DEFAULT_OVERLAP_PCT)
    child_splitter = _splitter(CHILD_SIZE, overlap_pct)
    chunks: list[Chunk] = []
    for s in sections:
        for i, parent in enumerate(parent_splitter.split_text(s.text)):
            key = f"{s.location}#{i}"
            chunks.append(Chunk(parent, s.location, s.ocr, parent_key=key, is_parent=True))
            chunks += [Chunk(c, s.location, s.ocr, parent_key=key) for c in child_splitter.split_text(parent) if c.strip()]
    return chunks


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return 1 - dot / (na * nb) if na and nb else 1.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 1.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


async def semantic(
    sections: list[Section], embed: Callable[[list[str]], Awaitable[list[list[float]]]], percentile: float = SEMANTIC_PERCENTILE
) -> list[Chunk]:
    """Break where the embedding distance between neighbouring sentences is in the top (100 − percentile)%."""
    chunks: list[Chunk] = []
    for s in sections:
        sentences = [x.strip() for x in SENTENCE.split(s.text) if x.strip()]
        if len(sentences) < 3:
            chunks += recursive([s])
            continue
        vectors = await embed(sentences)
        distances = [_cosine_distance(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        threshold = _percentile(distances, percentile)
        current = [sentences[0]]
        for sentence, dist in zip(sentences[1:], distances, strict=True):
            if (dist >= threshold or len(" ".join(current)) > CHUNK_SIZE) and current:
                chunks.append(Chunk(" ".join(current), s.location, s.ocr))
                current = []
            current.append(sentence)
        if current:
            chunks.append(Chunk(" ".join(current), s.location, s.ocr))
    return chunks


def default_strategy(ext: str) -> Strategy:
    return "table" if ext in {"xlsx", "csv", "tsv"} else "recursive"
