import pytest
from langchain_core.vectorstores import InMemoryVectorStore

from app.rag.retriever import Retriever, format_context


def test_ingest_splits_long_text_and_tags_source(retriever: Retriever, vector_store: InMemoryVectorStore) -> None:
    text = "\n\n".join(f"Paragraph {i}. " + "lorem ipsum " * 15 for i in range(6))
    n = retriever.ingest(text, source="doc.md", metadata={"team": "ml"})

    assert n > 1
    stored = list(vector_store.store.values())
    assert len(stored) == n
    assert all(d["metadata"] == {"team": "ml", "source": "doc.md"} for d in stored)
    assert all(len(d["text"]) <= 200 for d in stored)


def test_ingest_empty_text_stores_nothing(retriever: Retriever) -> None:
    assert retriever.ingest("   ", source="empty.md") == 0


def test_retrieve_returns_scored_chunks_with_source(retriever: Retriever) -> None:
    retriever.ingest("Paris is the capital of France.", source="geo.md")
    retriever.ingest("Bananas are rich in potassium.", source="food.md")

    chunks = retriever.retrieve("anything", k=2)
    assert len(chunks) == 2
    assert {c.source for c in chunks} == {"geo.md", "food.md"}
    assert all(isinstance(c.score, float) for c in chunks)


def test_retrieve_on_empty_store_returns_nothing(retriever: Retriever) -> None:
    assert retriever.retrieve("anything") == []


def test_overlap_must_be_smaller_than_chunk_size(vector_store: InMemoryVectorStore) -> None:
    with pytest.raises(ValueError):
        Retriever(vector_store, chunk_size=100, chunk_overlap=100, default_k=3)


def test_format_context_numbers_and_tags_documents(retriever: Retriever) -> None:
    retriever.ingest("Paris is the capital of France.", source="geo.md")
    context = format_context(retriever.retrieve("capital"))
    assert context.startswith('<document index="1" source="geo.md">')
    assert "Paris is the capital of France." in context
