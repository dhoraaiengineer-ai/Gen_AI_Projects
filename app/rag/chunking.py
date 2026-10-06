"""Chunking strategies: how a document is cut into the pieces that get embedded and retrieved.

- recursive:    fixed-size chunks split on paragraph -> sentence -> word boundaries. Cheap, predictable.
- semantic:     sentence groups, split where the meaning shifts (embedding distance between neighbours).
- parent_child: small child chunks are embedded for precise matching; retrieval returns the larger
                parent so the LLM still gets enough surrounding context.
- table:        tables are split between rows only, with the header repeated on every chunk; prose
                around them is chunked recursively.

Each strategy returns ready-to-store Documents; `Retriever` handles ids, storage and parent expansion.
"""

import csv
import io
import logging
import math
import re
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Metadata keys the chunkers write and the retriever reads.
STRATEGY_KEY = "chunking"
PARENT_ID_KEY = "parent_id"
PARENT_CONTENT_KEY = "parent_content"
CONTENT_TYPE_KEY = "content_type"


class ChunkingStrategy(StrEnum):
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    PARENT_CHILD = "parent_child"
    TABLE = "table"


class Chunker(Protocol):
    strategy: ChunkingStrategy

    def split(self, text: str, metadata: dict[str, str]) -> list[Document]: ...


def overlap_chars(chunk_size: int, overlap_pct: float) -> int:
    """Overlap as a share of the chunk size, so it scales when the chunk size changes."""
    if not 0 <= overlap_pct <= 50:
        raise ValueError("overlap_pct must be between 0 and 50")
    return int(chunk_size * overlap_pct / 100)


def _recursive_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


class RecursiveChunker:
    strategy = ChunkingStrategy.RECURSIVE

    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.splitter = _recursive_splitter(chunk_size, chunk_overlap)

    def split(self, text: str, metadata: dict[str, str]) -> list[Document]:
        meta = {**metadata, STRATEGY_KEY: self.strategy.value}
        return self.splitter.create_documents([text], metadatas=[meta])


# Sentence ends followed by whitespace, or blank lines (paragraph breaks, markdown blocks).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n\s*\n")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if s and s.strip()]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 1.0 - dot / norm if norm else 1.0


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolated percentile (same as numpy's default), without pulling in numpy."""
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


class SemanticChunker:
    """Groups consecutive sentences and starts a new chunk where the topic shifts.

    Each sentence is embedded together with its neighbours (a window of 1 on each side) to smooth out
    short sentences. A boundary goes wherever the distance between neighbouring windows is above the
    `breakpoint_percentile` of all distances in the document. Groups longer than `max_chunk_size` are
    split again recursively, so no chunk exceeds the size the other strategies use.
    """

    strategy = ChunkingStrategy.SEMANTIC

    def __init__(self, embeddings: Embeddings, breakpoint_percentile: float, max_chunk_size: int, chunk_overlap: int):
        if not 0 < breakpoint_percentile < 100:
            raise ValueError("breakpoint_percentile must be between 0 and 100")
        self.embeddings = embeddings
        self.breakpoint_percentile = breakpoint_percentile
        self.oversize_splitter = _recursive_splitter(max_chunk_size, chunk_overlap)

    def split(self, text: str, metadata: dict[str, str]) -> list[Document]:
        meta = {**metadata, STRATEGY_KEY: self.strategy.value}
        groups = self._group_sentences(split_sentences(text))
        return self.oversize_splitter.create_documents(groups, metadatas=[meta] * len(groups))

    def _group_sentences(self, sentences: list[str]) -> list[str]:
        if len(sentences) <= 2:
            return [" ".join(sentences)] if sentences else []

        windows = [" ".join(sentences[max(0, i - 1) : i + 2]) for i in range(len(sentences))]
        vectors = self.embeddings.embed_documents(windows)
        distances = [_cosine_distance(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        threshold = percentile(distances, self.breakpoint_percentile)

        groups: list[str] = []
        current = [sentences[0]]
        for sentence, distance in zip(sentences[1:], distances, strict=True):
            if distance > threshold:
                groups.append(" ".join(current))
                current = []
            current.append(sentence)
        groups.append(" ".join(current))
        logger.debug("semantic split", extra={"sentences": len(sentences), "groups": len(groups)})
        return groups


_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_DELIMITED_EXTENSIONS = {".csv": ",", ".tsv": "\t"}


def _markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(c.strip().replace("|", "\\|") for c in cells) + " |"


@dataclass(frozen=True)
class _Block:
    text: str
    header: str | None = None  # tables only: header + separator lines, repeated on every chunk
    rows: tuple[str, ...] = ()


def _blocks_from_markdown(text: str) -> list[_Block]:
    """Separate markdown pipe tables (header line, then a |---| line, then rows) from the prose around them."""
    lines = text.splitlines()
    blocks: list[_Block] = []
    prose: list[str] = []
    i = 0
    while i < len(lines):
        is_table = (
            lines[i].strip().startswith("|") and i + 1 < len(lines) and _TABLE_SEPARATOR.match(lines[i + 1]) is not None
        )
        if not is_table:
            prose.append(lines[i])
            i += 1
            continue
        if any(line.strip() for line in prose):
            blocks.append(_Block("\n".join(prose)))
        prose = []
        header = f"{lines[i].strip()}\n{lines[i + 1].strip()}"
        i += 2
        rows: list[str] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append(lines[i].strip())
            i += 1
        blocks.append(_Block(header, header=header, rows=tuple(rows)))
    if any(line.strip() for line in prose):
        blocks.append(_Block("\n".join(prose)))
    return blocks


def _block_from_delimited(text: str, delimiter: str) -> list[_Block]:
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
    if not rows:
        return []
    header = f"{_markdown_row(rows[0])}\n{_markdown_row(['---'] * len(rows[0]))}"
    return [_Block(header, header=header, rows=tuple(_markdown_row(r) for r in rows[1:]))]


class TableAwareChunker:
    """Keeps tables intact: rows are never cut in half, and every table chunk repeats the header row so
    the LLM knows what each column means. Handles markdown pipe tables inside any document, and whole
    .csv / .tsv files (rendered as markdown tables). Prose between tables is chunked recursively."""

    strategy = ChunkingStrategy.TABLE

    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.prose_splitter = _recursive_splitter(chunk_size, chunk_overlap)

    def split(self, text: str, metadata: dict[str, str]) -> list[Document]:
        source = metadata.get("source", "").lower()
        delimiter = next((d for ext, d in _DELIMITED_EXTENSIONS.items() if source.endswith(ext)), None)
        blocks = _block_from_delimited(text, delimiter) if delimiter else _blocks_from_markdown(text)

        docs: list[Document] = []
        for block in blocks:
            if block.header is None:
                meta = {**metadata, STRATEGY_KEY: self.strategy.value, CONTENT_TYPE_KEY: "text"}
                docs.extend(self.prose_splitter.create_documents([block.text], metadatas=[meta]))
                continue
            meta = {**metadata, STRATEGY_KEY: self.strategy.value, CONTENT_TYPE_KEY: "table"}
            chunks = self._table_chunks(block.header, block.rows)
            docs.extend(Document(page_content=chunk, metadata=meta) for chunk in chunks)
        return docs

    def _table_chunks(self, header: str, rows: tuple[str, ...]) -> list[str]:
        if not rows:
            return [header]
        chunks: list[str] = []
        current: list[str] = []
        size = len(header)
        for row in rows:
            # A row longer than chunk_size still goes out whole: a cut row is worse than a long chunk.
            if current and size + 1 + len(row) > self.chunk_size:
                chunks.append("\n".join([header, *current]))
                current, size = [], len(header)
            current.append(row)
            size += 1 + len(row)
        chunks.append("\n".join([header, *current]))
        return chunks


class ParentChildChunker:
    """Splits into large parents, then each parent into small children. Only children are embedded;
    each child carries its parent's id and text, which the retriever returns instead of the child."""

    strategy = ChunkingStrategy.PARENT_CHILD

    def __init__(self, parent_chunk_size: int, child_chunk_size: int, chunk_overlap: int, child_chunk_overlap: int):
        if child_chunk_size >= parent_chunk_size:
            raise ValueError("child_chunk_size must be smaller than parent_chunk_size")
        self.parent_splitter = _recursive_splitter(parent_chunk_size, chunk_overlap)
        self.child_splitter = _recursive_splitter(child_chunk_size, child_chunk_overlap)

    def split(self, text: str, metadata: dict[str, str]) -> list[Document]:
        children: list[Document] = []
        for index, parent in enumerate(self.parent_splitter.split_text(text)):
            parent_id = content_id(metadata.get("source", ""), self.strategy, f"{index}:{parent}")
            meta = {
                **metadata,
                STRATEGY_KEY: self.strategy.value,
                PARENT_ID_KEY: parent_id,
                PARENT_CONTENT_KEY: parent,
            }
            children.extend(self.child_splitter.create_documents([parent], metadatas=[meta]))
        return children


_ID_NAMESPACE = uuid.UUID("6f1c2b1e-3c55-4a43-9a0e-5d8f2f0c7a11")


def content_id(source: str, strategy: ChunkingStrategy, content: str) -> str:
    """Deterministic id: re-ingesting the same text from the same source overwrites instead of duplicating."""
    return str(uuid.uuid5(_ID_NAMESPACE, f"{source}\x00{strategy.value}\x00{content}"))
