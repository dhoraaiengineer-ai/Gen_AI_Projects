"""Hybrid search, reciprocal rank fusion, LLM re-ranking and the hallucination guard."""

from functools import partial

import pytest
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import Settings
from app.container import build_chunker
from app.rag.grounding import check_grounding
from app.rag.registry import InMemoryDocumentRegistry
from app.rag.rerank import LLMReranker, parse_ranking
from app.rag.retriever import InMemoryKeywordSearch, RetrievedChunk, Retriever, reciprocal_rank_fusion
from tests.conftest import AppHarness, fake_llm


def _doc(text: str, source: str = "s.md", id: str | None = None) -> Document:
    return Document(id=id or text, page_content=text, metadata={"source": source})


def _chunk(text: str, source: str = "s.md") -> RetrievedChunk:
    return RetrievedChunk(_doc(text, source), 1.0)


# ---------- reciprocal rank fusion ----------


def test_rrf_rewards_agreement_between_lists() -> None:
    a, b, c = _doc("a"), _doc("b"), _doc("c")
    fused = reciprocal_rank_fusion([[(a, 0.9), (b, 0.8), (c, 0.7)], [(c, 5.0), (a, 1.0)]])
    assert [d.page_content for d, _ in fused] == ["a", "c", "b"]  # a: ranks 1+2, c: 3+1, b: 2 only
    assert fused[0][1] <= 1.0


def test_rrf_with_one_list_keeps_order_and_scores() -> None:
    a, b = _doc("a"), _doc("b")
    assert reciprocal_rank_fusion([[(a, 0.9), (b, 0.5)], []]) == [(a, 0.9), (b, 0.5)]
    assert reciprocal_rank_fusion([]) == []


# ---------- keyword + hybrid retrieval ----------


@pytest.fixture
def hybrid(vector_store: InMemoryVectorStore, settings: Settings) -> Retriever:
    return Retriever(
        vector_store,
        partial(build_chunker, settings, vector_store.embeddings),
        settings.chunking_strategy,
        settings.top_k,
        InMemoryDocumentRegistry(),
        keyword_search=InMemoryKeywordSearch(vector_store),
    )


def test_keyword_search_ignores_stopwords_and_ranks_by_overlap(vector_store: InMemoryVectorStore) -> None:
    vector_store.add_documents([_doc("DOI: 10.5555/jawe.2024.0317"), _doc("The article is about delay spread.")])
    hits = InMemoryKeywordSearch(vector_store).search("What is the DOI?", 5)
    assert [d.page_content for d, _ in hits] == ["DOI: 10.5555/jawe.2024.0317"]


def test_hybrid_search_finds_exact_identifiers(hybrid: Retriever) -> None:
    hybrid.ingest_text("PUBLICATION DETAILS. DOI: 10.5555/jawe.2024.0317. Pages 41-52.", source="cert.pdf")
    for i in range(8):
        hybrid.ingest_text(f"Unrelated note number {i} about antennas and buildings.", source=f"n{i}.md")
    sources = [c.source for c in hybrid.retrieve("What is the DOI of the article?", k=2)]
    assert "cert.pdf" in sources


def test_multi_query_retrieval_merges_phrasings(hybrid: Retriever) -> None:
    hybrid.ingest_text("The ISSN is 2799-0417.", source="cert.pdf")
    hybrid.ingest_text("Measurements were taken at five sites.", source="faq.md")
    sources = {c.source for c in hybrid.retrieve(["How many sites?", "What is the ISSN?"], k=2)}
    assert sources == {"cert.pdf", "faq.md"}


# ---------- re-ranking ----------


def test_parse_ranking_tolerates_prose_and_drops_bad_indexes() -> None:
    assert parse_ranking("Best first: [3, 1, 3, 9, 2]", candidates=3) == [2, 0, 1]
    with pytest.raises(ValueError):
        parse_ranking("passage three", candidates=3)


def test_reranker_orders_by_the_llm_and_keeps_unranked_after() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    reranked = LLMReranker(fake_llm("[3, 1]")).rerank("q", chunks, k=3)
    assert [c.document.page_content for c in reranked] == ["c", "a", "b"]


def test_reranker_failure_keeps_the_fused_order() -> None:
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    assert LLMReranker(fake_llm("no idea")).rerank("q", chunks, k=2) == chunks[:2]


def test_retriever_reranks_a_wider_candidate_pool(hybrid: Retriever) -> None:
    for i in range(6):
        hybrid.ingest_text(f"Passage number {i} about delay spread.", source=f"p{i}.md")
    hybrid.reranker = LLMReranker(fake_llm("[6, 5]"))
    hybrid.rerank_candidates = 6
    top = hybrid.retrieve("delay spread", k=2)
    assert len(top) == 2
    assert all(c.document.page_content.startswith("Passage number") for c in top)
    assert hybrid.retrieve("delay spread", k=2, rerank=False)  # the agent path skips the LLM


# ---------- hallucination guard ----------


CERT = [_chunk("Journal impact factor: 4.21. ISSN 2799-0417. DOI: 10.5555/jawe.2024.0317")]


@pytest.mark.parametrize(
    ("answer", "grounded", "issue"),
    [
        ("The ISSN is 2799-0417 [1].", True, None),
        ("The DOI is 10.5555/jawe.2024.0317 [1].", True, None),
        ("The impact factor is 5.3 [1].", False, "values not found in the documents: 5.3"),
        ("The ISSN is 2799-0417.", False, "no citations"),
        ("The ISSN is 2799-0417 [2].", False, "cites passages that were not provided: [2]"),
    ],
)
def test_grounding_checks(answer: str, grounded: bool, issue: str | None) -> None:
    report = check_grounding(answer, CERT)
    assert report.grounded is grounded
    if issue:
        assert issue in report.issues


def test_refusal_is_not_a_hallucination() -> None:
    report = check_grounding("The documents don't contain this information.", CERT)
    assert report.grounded and report.refusal


def test_api_flags_ungrounded_answers_and_does_not_cache_them(harness: AppHarness) -> None:
    ingest = {"documents": [{"text": "Journal impact factor: 4.21.", "source": "cert.pdf"}]}
    with harness.client("The impact factor is 9.9 [1].", "The impact factor is 4.21 [1].") as c:
        c.post("/api/v1/ingest", json=ingest)
        first = c.post("/api/v1/query", json={"question": "What is the impact factor?"}).json()
        second = c.post("/api/v1/query", json={"question": "What is the impact factor?"}).json()

    assert first["grounded"] is False
    assert "values not found in the documents: 9.9" in first["grounding_issues"]
    assert second["cached"] is False and second["grounded"] is True  # the bad answer was never cached


def test_block_mode_replaces_ungrounded_answers(harness: AppHarness) -> None:
    harness.settings.hallucination_guard = "block"
    with harness.client("The impact factor is 9.9 [1].") as c:
        c.post("/api/v1/ingest", json={"documents": [{"text": "Journal impact factor: 4.21.", "source": "c.pdf"}]})
        r = c.post("/api/v1/query", json={"question": "Impact factor?"}).json()
    assert r["answer"].startswith("I couldn't find a well-supported answer")
    assert r["sources"]  # the user can still check the passages


def test_temperature_must_stay_between_02_and_05() -> None:
    assert Settings(_env_file=None).llm_temperature == 0.2
    for bad in (0.0, 0.7):
        with pytest.raises(ValueError):
            Settings(_env_file=None, llm_temperature=bad)
