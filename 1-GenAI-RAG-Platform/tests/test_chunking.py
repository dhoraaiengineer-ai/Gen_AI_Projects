import pytest
from langchain_core.embeddings import Embeddings

from app.config import Settings
from app.container import build_chunker
from app.rag.chunking import (
    PARENT_CONTENT_KEY,
    PARENT_ID_KEY,
    ChunkingStrategy,
    ParentChildChunker,
    RecursiveChunker,
    SemanticChunker,
    TableAwareChunker,
    content_id,
    overlap_chars,
    percentile,
    split_sentences,
)


class TopicEmbeddings(Embeddings):
    """One axis per topic keyword, so sentences about the same topic embed close together."""

    TOPICS = ("cat", "rocket", "bread")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float(lowered.count(topic)) + 0.01 for topic in self.TOPICS]


def test_recursive_respects_chunk_size_and_tags_strategy() -> None:
    text = "\n\n".join("word " * 40 for _ in range(5))
    docs = RecursiveChunker(chunk_size=100, chunk_overlap=10).split(text, {"source": "a.md"})

    assert len(docs) > 1
    assert all(len(d.page_content) <= 100 for d in docs)
    assert all(d.metadata == {"source": "a.md", "chunking": "recursive"} for d in docs)


def test_recursive_rejects_overlap_not_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        RecursiveChunker(chunk_size=100, chunk_overlap=100)


def test_split_sentences_on_punctuation_and_blank_lines() -> None:
    assert split_sentences("One. Two? Three!\n\nFour\nstill four.") == ["One.", "Two?", "Three!", "Four\nstill four."]


def test_percentile_interpolates() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert percentile([5.0], 90) == 5.0


def test_semantic_splits_where_the_topic_changes() -> None:
    text = (
        "The cat sleeps. The cat purrs. A cat likes fish. "
        "The rocket launched. The rocket reached orbit. A rocket needs fuel. "
        "Fresh bread smells good. Bread needs yeast. Bake bread at dawn."
    )
    chunker = SemanticChunker(TopicEmbeddings(), breakpoint_percentile=70, max_chunk_size=1000, chunk_overlap=0)
    docs = chunker.split(text, {"source": "mixed.md"})

    assert [d.page_content for d in docs] == [
        "The cat sleeps. The cat purrs. A cat likes fish.",
        "The rocket launched. The rocket reached orbit. A rocket needs fuel.",
        "Fresh bread smells good. Bread needs yeast. Bake bread at dawn.",
    ]
    assert all(d.metadata["chunking"] == "semantic" for d in docs)


def test_semantic_caps_long_groups_at_max_chunk_size() -> None:
    text = " ".join(f"The cat number {i} sleeps on the mat." for i in range(40))
    chunker = SemanticChunker(TopicEmbeddings(), breakpoint_percentile=95, max_chunk_size=200, chunk_overlap=0)
    assert all(len(d.page_content) <= 200 for d in chunker.split(text, {}))


def test_semantic_handles_short_and_empty_text() -> None:
    chunker = SemanticChunker(TopicEmbeddings(), breakpoint_percentile=90, max_chunk_size=500, chunk_overlap=0)
    assert chunker.split("", {}) == []
    assert [d.page_content for d in chunker.split("Just one sentence.", {})] == ["Just one sentence."]


def test_semantic_rejects_invalid_percentile() -> None:
    with pytest.raises(ValueError):
        SemanticChunker(TopicEmbeddings(), breakpoint_percentile=100, max_chunk_size=500, chunk_overlap=0)


def test_parent_child_children_point_at_their_parent() -> None:
    text = "\n\n".join(f"Part {i}. " + "lorem ipsum " * 30 for i in range(3))
    chunker = ParentChildChunker(parent_chunk_size=400, child_chunk_size=100, chunk_overlap=0, child_chunk_overlap=0)
    children = chunker.split(text, {"source": "p.md"})

    parents = {c.metadata[PARENT_ID_KEY]: c.metadata[PARENT_CONTENT_KEY] for c in children}
    assert 1 < len(parents) < len(children)
    assert all(len(c.page_content) <= 100 for c in children)
    assert all(c.page_content in c.metadata[PARENT_CONTENT_KEY] for c in children)
    assert all(len(p) <= 400 for p in parents.values())


def test_parent_child_requires_children_smaller_than_parents() -> None:
    with pytest.raises(ValueError):
        ParentChildChunker(parent_chunk_size=100, child_chunk_size=100, chunk_overlap=0, child_chunk_overlap=0)


def test_content_id_is_stable_and_distinguishes_inputs() -> None:
    a = content_id("a.md", ChunkingStrategy.RECURSIVE, "text")
    assert a == content_id("a.md", ChunkingStrategy.RECURSIVE, "text")
    assert a != content_id("b.md", ChunkingStrategy.RECURSIVE, "text")
    assert a != content_id("a.md", ChunkingStrategy.SEMANTIC, "text")


def test_build_chunker_supports_every_strategy(settings: Settings) -> None:
    for strategy in ChunkingStrategy:
        assert build_chunker(settings, TopicEmbeddings(), strategy).strategy == strategy


def test_semantic_needs_embeddings(settings: Settings) -> None:
    with pytest.raises(ValueError):
        build_chunker(settings, None, ChunkingStrategy.SEMANTIC)


def test_overlap_chars_is_a_share_of_chunk_size() -> None:
    assert overlap_chars(1000, 15) == 150
    assert overlap_chars(400, 10) == 40
    with pytest.raises(ValueError):
        overlap_chars(1000, 60)


def test_default_overlaps_differ_for_chunks_and_children() -> None:
    settings = Settings(_env_file=None, parent_chunk_size=2000, child_chunk_size=400)
    chunker = build_chunker(settings, None, ChunkingStrategy.PARENT_CHILD)
    assert isinstance(chunker, ParentChildChunker)
    assert chunker.parent_splitter._chunk_overlap == 300  # 15% of 2000
    assert chunker.child_splitter._chunk_overlap == 40  # 10% of 400


def test_overlap_override_applies_to_the_upload() -> None:
    chunker = build_chunker(Settings(_env_file=None, chunk_size=1000), None, ChunkingStrategy.RECURSIVE, 20)
    assert isinstance(chunker, RecursiveChunker)
    assert chunker.splitter._chunk_overlap == 200


def _table_chunker(chunk_size: int = 120) -> TableAwareChunker:
    return TableAwareChunker(chunk_size=chunk_size, chunk_overlap=0)


def test_table_chunks_split_between_rows_and_repeat_the_header() -> None:
    rows = "\n".join(f"| item-{i} | {i * 10} |" for i in range(12))
    text = f"Prices below.\n\n| Item | Price |\n|---|---|\n{rows}\n\nPrices include tax."
    docs = _table_chunker().split(text, {"source": "prices.md"})

    tables = [d for d in docs if d.metadata["content_type"] == "table"]
    prose = [d.page_content for d in docs if d.metadata["content_type"] == "text"]
    assert len(tables) > 1
    assert all(t.page_content.startswith("| Item | Price |\n|---|---|\n| item-") for t in tables)
    body_rows = [line for t in tables for line in t.page_content.splitlines()[2:]]
    assert body_rows == rows.splitlines()  # every row exactly once, none cut
    assert prose == ["Prices below.", "Prices include tax."]
    assert all(d.metadata["chunking"] == "table" for d in docs)


def test_table_keeps_an_oversized_row_whole() -> None:
    long_cell = "x" * 300
    text = f"| A | B |\n|---|---|\n| 1 | {long_cell} |\n| 2 | short |"
    docs = _table_chunker().split(text, {})
    assert any(long_cell in d.page_content for d in docs)
    assert all(d.page_content.startswith("| A | B |") for d in docs)


def test_csv_file_becomes_markdown_table_chunks() -> None:
    text = 'name,city\nAsha,Tokyo\n"Ravi, Jr.",Osaka\n\n'
    docs = _table_chunker(chunk_size=1000).split(text, {"source": "people.CSV"})
    assert [d.page_content for d in docs] == ["| name | city |\n| --- | --- |\n| Asha | Tokyo |\n| Ravi, Jr. | Osaka |"]


def test_tsv_and_pipe_escaping() -> None:
    docs = _table_chunker(chunk_size=1000).split("a\tb\nx|y\tz\n", {"source": "t.tsv"})
    assert docs[0].page_content.splitlines()[-1] == r"| x\|y | z |"


def test_text_without_tables_is_plain_prose() -> None:
    docs = _table_chunker().split("Just | a pipe in prose.\nNo table here.", {})
    assert [d.metadata["content_type"] for d in docs] == ["text"]
