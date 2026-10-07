"""Tracks what has been ingested per source, so re-uploads are incremental.

One record per source: a fingerprint of the content + chunking settings, and the ids of its chunks.
Same fingerprint -> skip. Different -> embed only the new chunks and delete the ones that disappeared.
The Postgres implementation lives in providers.py; this in-memory one is for tests.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DocumentRecord:
    source: str
    content_hash: str
    chunking: str
    chunk_ids: tuple[str, ...]


class DocumentRegistry(Protocol):
    def get(self, source: str) -> DocumentRecord | None: ...

    def put(self, record: DocumentRecord) -> None: ...

    def delete(self, source: str) -> None: ...

    def list(self) -> list[DocumentRecord]: ...


class InMemoryDocumentRegistry:
    def __init__(self) -> None:
        self.records: dict[str, DocumentRecord] = {}

    def get(self, source: str) -> DocumentRecord | None:
        return self.records.get(source)

    def put(self, record: DocumentRecord) -> None:
        self.records[record.source] = record

    def delete(self, source: str) -> None:
        self.records.pop(source, None)

    def list(self) -> list[DocumentRecord]:
        return sorted(self.records.values(), key=lambda r: r.source)
