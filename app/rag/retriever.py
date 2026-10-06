"""Ingestion (split + embed + store) and retrieval over any LangChain vector store."""

import logging
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    document: Document
    score: float

    @property
    def source(self) -> str:
        return str(self.document.metadata.get("source", "unknown"))


class Retriever:
    def __init__(self, vector_store: VectorStore, chunk_size: int, chunk_overlap: int, default_k: int):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.vector_store = vector_store
        self.default_k = default_k
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def ingest(self, text: str, source: str, metadata: dict[str, str] | None = None) -> int:
        base = {**(metadata or {}), "source": source}
        chunks = self.splitter.create_documents([text], metadatas=[base])
        if not chunks:
            return 0
        self.vector_store.add_documents(chunks)
        logger.info("ingested document", extra={"source": source, "chunks": len(chunks)})
        return len(chunks)

    def retrieve(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        results = self.vector_store.similarity_search_with_relevance_scores(query, k=k or self.default_k)
        return [RetrievedChunk(doc, float(score)) for doc, score in results]


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render chunks as numbered, source-tagged documents the model can cite as [1], [2], ..."""
    return "\n\n".join(
        f'<document index="{i}" source="{c.source}">\n{c.document.page_content}\n</document>'
        for i, c in enumerate(chunks, start=1)
    )
