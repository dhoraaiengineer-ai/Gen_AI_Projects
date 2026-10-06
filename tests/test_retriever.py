import pytest
from langchain_core.vectorstores import InMemoryVectorStore

from app.rag.chunking import ChunkingStrategy, RecursiveChunker
from app.rag.loaders import Section
from app.rag.registry import InMemoryDocumentRegistry
from app.rag.retriever import IngestStatus, Retriever, format_context


def test_ingest_splits_long_text_and_tags_source(retriever: Retriever, vector_store: InMemoryVectorStore) -> None:
    text = "\n\n".join(f"Paragraph {i}. " + "lorem ipsum " * 15 for i in range(6))
    n = retriever.ingest_text(text, source="doc.md", metadata={"team": "ml"}).chunks

    assert n > 1
    stored = list(vector_store.store.values())
    assert len(stored) == n
    assert all(d["metadata"] == {"team": "ml", "source": "doc.md", "chunking": "recursive"} for d in stored)
    assert all(len(d["text"]) <= 200 for d in stored)


def test_ingest_empty_text_stores_nothing(retriever: Retriever) -> None:
    result = retriever.ingest_text("   ", source="empty.md")
    assert result.status == IngestStatus.EMPTY
    assert result.chunks == 0


def test_retrieve_returns_scored_chunks_with_source(retriever: Retriever) -> None:
    retriever.ingest_text("Paris is the capital of France.", source="geo.md")
    retriever.ingest_text("Bananas are rich in potassium.", source="food.md")

    chunks = retriever.retrieve("anything", k=2)
    assert len(chunks) == 2
    assert {c.source for c in chunks} == {"geo.md", "food.md"}
    assert all(isinstance(c.score, float) for c in chunks)


def test_retrieve_on_empty_store_returns_nothing(retriever: Retriever) -> None:
    assert retriever.retrieve("anything") == []


def test_misconfigured_default_strategy_fails_at_startup(vector_store: InMemoryVectorStore) -> None:
    def factory(strategy: ChunkingStrategy, overlap_pct: float | None) -> RecursiveChunker:
        return RecursiveChunker(chunk_size=100, chunk_overlap=100)  # invalid: overlap == size

    with pytest.raises(ValueError):
        Retriever(vector_store, factory, ChunkingStrategy.RECURSIVE, 3, InMemoryDocumentRegistry())


def test_reingesting_the_same_document_does_not_duplicate(
    retriever: Retriever, vector_store: InMemoryVectorStore
) -> None:
    text = "\n\n".join(f"Paragraph {i}. " + "lorem ipsum " * 15 for i in range(4))
    first = retriever.ingest_text(text, source="doc.md")
    second = retriever.ingest_text(text, source="doc.md")

    assert first.status == IngestStatus.ADDED
    assert second.status == IngestStatus.UNCHANGED
    assert second.added == 0
    assert len(vector_store.store) == first.chunks


def test_retrieve_skips_duplicate_chunks(vector_store: InMemoryVectorStore, retriever: Retriever) -> None:
    # Rows stored before ids were deterministic: same text, different ids.
    vector_store.add_texts(["Paris is the capital of France."] * 3, metadatas=[{"source": "geo.md"}] * 3)
    vector_store.add_texts(["Bananas are rich in potassium."], metadatas=[{"source": "food.md"}])

    chunks = retriever.retrieve("capital", k=2)
    assert sorted(c.document.page_content for c in chunks) == [
        "Bananas are rich in potassium.",
        "Paris is the capital of France.",
    ]


def test_parent_child_returns_each_parent_once_with_full_text(retriever: Retriever) -> None:
    text = "\n\n".join(f"Section {i}. " + "alpha beta gamma " * 20 for i in range(3))
    stored = retriever.ingest_text(text, source="doc.md", strategy=ChunkingStrategy.PARENT_CHILD).chunks

    chunks = retriever.retrieve("alpha", k=10)
    parent_ids = [c.document.metadata["parent_id"] for c in chunks]
    assert len(parent_ids) == len(set(parent_ids))  # siblings collapsed into one result per parent
    assert len(chunks) < stored
    assert all(len(c.document.page_content) > 100 for c in chunks)  # parent text, not the 100-char child
    assert all("parent_content" not in c.document.metadata for c in chunks)


def test_format_context_numbers_and_tags_documents(retriever: Retriever) -> None:
    retriever.ingest_text("Paris is the capital of France.", source="geo.md")
    context = format_context(retriever.retrieve("capital"))
    assert context.startswith('<document index="1" source="geo.md">')
    assert "Paris is the capital of France." in context


def _paragraphs(*texts: str) -> str:
    return "\n\n".join(t + " " + "filler words to pad the paragraph " * 4 for t in texts)


def test_editing_a_document_embeds_only_new_chunks_and_deletes_stale_ones(
    retriever: Retriever, vector_store: InMemoryVectorStore
) -> None:
    first = retriever.ingest_text(_paragraphs("Alpha.", "Beta.", "Gamma."), source="doc.md")
    second = retriever.ingest_text(_paragraphs("Alpha.", "Beta.", "Delta."), source="doc.md")

    assert second.status == IngestStatus.UPDATED
    assert 0 < second.added < first.chunks  # unchanged paragraphs keep their embeddings
    assert second.removed == second.added
    texts = [d["text"] for d in vector_store.store.values()]
    assert len(texts) == second.chunks
    assert not any(t.startswith("Gamma.") for t in texts)
    assert any(t.startswith("Delta.") for t in texts)


def test_changing_the_chunking_strategy_rechunks_the_document(retriever: Retriever) -> None:
    text = _paragraphs("Alpha.", "Beta.")
    retriever.ingest_text(text, source="doc.md")
    result = retriever.ingest_text(text, source="doc.md", strategy=ChunkingStrategy.PARENT_CHILD)
    assert result.status == IngestStatus.UPDATED
    assert result.chunking == ChunkingStrategy.PARENT_CHILD


def test_repeated_text_inside_a_document_is_stored_once(
    retriever: Retriever, vector_store: InMemoryVectorStore
) -> None:
    result = retriever.ingest(
        "doc.pdf",
        [Section("Same footer text.", {"page": "1"}), Section("Same footer text.", {"page": "2"})],
    )
    assert result.chunks == 1
    assert len(vector_store.store) == 1


def test_emptying_a_document_removes_its_chunks(retriever: Retriever, vector_store: InMemoryVectorStore) -> None:
    retriever.ingest_text("Some content here.", source="doc.md")
    result = retriever.ingest_text("   ", source="doc.md")
    assert result.status == IngestStatus.EMPTY
    assert result.removed == 1
    assert vector_store.store == {}


def test_citations_include_the_page(retriever: Retriever) -> None:
    retriever.ingest("report.pdf", [Section("Revenue grew in March.", {"page": "3"})])
    [chunk] = retriever.retrieve("revenue", k=1)
    assert chunk.citation == "report.pdf, p. 3"
    assert format_context([chunk]).startswith('<document index="1" source="report.pdf, p. 3">')


def test_windows_and_unix_line_endings_are_the_same_document(retriever: Retriever) -> None:
    retriever.ingest_text("Line one.\r\n\r\nLine two.", source="doc.txt")
    assert retriever.ingest_text("Line one.\n\nLine two.", source="doc.txt").status == IngestStatus.UNCHANGED


def test_fullwidth_citations_become_brackets() -> None:
    from app.rag.retriever import normalize_citations

    assert normalize_citations("Paris 【1】 and Lyon 【2†L3-L5】.") == "Paris [1] and Lyon [2]."
    assert normalize_citations("Plain [1].") == "Plain [1]."
