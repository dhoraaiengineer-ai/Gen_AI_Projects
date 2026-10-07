"""Metadata filtering: restrict retrieval to some documents, file types or tags.

Every chunk carries metadata: `source` (file name), `file_type` (extension), `tags` (stored as ",a,b,") plus
its location (page / sheet / slide) and OCR / guardrail flags. A filter is applied inside both searches
(vector and keyword), so top_k is filled from matching chunks only, not cut down after the fact.

File types are matched on the source's extension, so documents ingested before `file_type` existed
filter correctly too.
"""

from dataclasses import dataclass
from pathlib import PurePath
from typing import Any


def file_type_of(source: str) -> str:
    return PurePath(source).suffix.lower().lstrip(".")


def normalize_tags(tags: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not tags:
        return ()
    items = tags.split(",") if isinstance(tags, str) else tags
    return tuple(sorted({t.strip().lower() for t in items if t and t.strip()}))


def tags_field(tags: tuple[str, ...]) -> str:
    """Stored form: ',finance,policy,' so a tag matches with LIKE '%,tag,%' and never as a substring."""
    return f",{','.join(tags)}," if tags else ""


@dataclass(frozen=True)
class MetadataFilter:
    sources: tuple[str, ...] = ()
    file_types: tuple[str, ...] = ()  # extensions without the dot: "pdf", "xlsx"
    tags: tuple[str, ...] = ()

    @classmethod
    def build(
        cls,
        sources: list[str] | None = None,
        file_types: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> "MetadataFilter | None":
        f = cls(
            tuple(sorted(set(sources or []))),
            tuple(sorted({t.lower().lstrip(".") for t in file_types or []})),
            normalize_tags(tags),
        )
        return None if f.is_empty else f

    @property
    def is_empty(self) -> bool:
        return not (self.sources or self.file_types or self.tags)

    def matches(self, metadata: dict[str, Any]) -> bool:
        source = str(metadata.get("source", ""))
        if self.sources and source not in self.sources:
            return False
        if self.file_types and file_type_of(source) not in self.file_types:
            return False
        if self.tags:
            stored = str(metadata.get("tags", ""))
            if not any(f",{t}," in stored for t in self.tags):
                return False
        return True

    def cache_key(self) -> str:
        return f"s={'|'.join(self.sources)};t={'|'.join(self.file_types)};g={'|'.join(self.tags)}"

    def describe(self) -> str:
        parts = []
        if self.sources:
            parts.append(f"documents: {', '.join(self.sources)}")
        if self.file_types:
            parts.append(f"types: {', '.join(self.file_types)}")
        if self.tags:
            parts.append(f"tags: {', '.join(self.tags)}")
        return "; ".join(parts)


def to_pgvector_filter(f: MetadataFilter) -> dict[str, Any]:
    """The langchain-postgres JSONB filter syntax."""
    clauses: list[dict[str, Any]] = []
    if f.sources:
        clauses.append({"source": {"$in": list(f.sources)}})
    if f.file_types:
        ext = [{"source": {"$ilike": f"%.{t}"}} for t in f.file_types]
        clauses.append(ext[0] if len(ext) == 1 else {"$or": ext})
    if f.tags:
        tag = [{"tags": {"$ilike": f"%,{t},%"}} for t in f.tags]
        clauses.append(tag[0] if len(tag) == 1 else {"$or": tag})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def to_callable_filter(f: MetadataFilter) -> Any:
    """InMemoryVectorStore takes a predicate over Documents (tests, local experiments)."""
    return lambda doc: f.matches(doc.metadata)
