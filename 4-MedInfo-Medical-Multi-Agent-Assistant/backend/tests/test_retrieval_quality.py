"""Stage 3: hybrid search, RRF, LLM re-ranking, multi-query follow-ups, filters, guideline versions."""

from __future__ import annotations

from datetime import date

import pytest

from app.agents.rag_graph import build_rag_graph
from app.core.audit import AuditLogger
from app.rag.chunking import Chunker
from app.rag.ingest import IngestService, Provenance, TrustedSources
from app.rag.interfaces import Passage, SearchFilter
from app.rag.memory_store import InMemoryRegistry, InMemoryVectorIndex
from app.rag.prompts import AnswerMode, format_passages
from app.rag.providers import filter_sql
from app.rag.rerank import LLMReranker, MultiQueryExpander
from app.rag.retrieval import HybridRetriever, reciprocal_rank_fusion
from app.rag.versions import apply_version_preference
from tests.fakes import FakeChatModel, FakeEmbedder, cited

PUB = "Synthetic Health Guidance Board (SYNTHETIC)"
T, U = "t_trusted", "t_user"


class BlindEmbedder(FakeEmbedder):
    """Every text gets the same vector: vector search can't tell passages apart (keyword must)."""

    def _vec(self, text: str) -> list[float]:
        return [1.0] * self.dimensions


def build(embedder=None, reranker=None):
    index, registry = InMemoryVectorIndex(), InMemoryRegistry()
    emb = embedder or FakeEmbedder()
    ingest = IngestService(
        registry=registry,
        index=index,
        embedder=emb,
        chunker=Chunker("recursive", chunk_size=500),
        ocr=None,
        trusted_sources=TrustedSources.load(),
        trusted_collection=T,
        user_collection=U,
        max_bytes=10**6,
        audit=AuditLogger(False),
    )
    retriever = HybridRetriever(
        index=index,
        embedder=emb,
        registry=registry,
        trusted_collection=T,
        user_collection=U,
        min_similarity=0.0,
        reranker=reranker,
        candidates=12,
    )
    return ingest, retriever


def add(ingest, name: str, text: str, **prov) -> None:
    meta = {"title": name, "publisher": PUB, "publication_date": date(2024, 1, 1), **prov}
    ingest.ingest_trusted(f"{name}.md", text.encode(), Provenance(**meta), actor_id="a")


def test_rrf_rewards_agreement() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert max(fused, key=fused.get) in {"a", "b"}
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert fused["d"] < fused["c"] or fused["d"] == pytest.approx(1 / 63)


def test_keyword_search_rescues_exact_codes() -> None:
    ingest, retriever = build(embedder=BlindEmbedder())
    for i in range(6):
        add(ingest, f"filler{i}", f"General synthetic guidance number {i} about wellbeing and sleep.")
    add(ingest, "code", "Product code ZXR4471 identifies the Zentoril 10 mg tablet pack (SYNTHETIC).")
    hits = retriever.retrieve("What is ZXR4471?", 3, SearchFilter())
    assert hits[0].title == "code"


def test_reranker_orders_and_drops_off_topic() -> None:
    ingest, _ = build()
    add(ingest, "bp", "Hypertension means raised blood pressure (SYNTHETIC).")
    add(ingest, "asthma", "Asthma causes wheeze and blood pressure is not discussed (SYNTHETIC).")
    rer = LLMReranker(FakeChatModel(rerank='{"relevant": [2]}'))
    _, retriever = build()
    retriever._index, retriever._registry = ingest._index, ingest._registry  # share the populated stores
    retriever._reranker = rer
    hits = retriever.retrieve("blood pressure", 5, SearchFilter())
    assert len(hits) == 1


def test_reranker_failure_falls_back_to_fused_order() -> None:
    cands = [Passage(id=str(i), text=f"t{i}", source="s", publisher=PUB, title=f"p{i}") for i in range(4)]
    out = LLMReranker(FakeChatModel(rerank=RuntimeError("down"))).rerank("q", cands, 3)
    assert [p.id for p in out] == ["0", "1", "2"]


def test_reranker_ignores_out_of_range_and_duplicates() -> None:
    cands = [Passage(id=str(i), text="t", source="s", publisher=PUB, title=f"p{i}") for i in range(3)]
    out = LLMReranker(FakeChatModel(rerank='{"relevant": [3, 3, 9, "x", 1]}')).rerank("q", cands, 5)
    assert [p.id for p in out] == ["2", "0"]


def test_multi_query_only_for_follow_ups() -> None:
    model = FakeChatModel(
        multi_query='{"standalone": "Zentoril use in pregnancy", "alternatives": ["Zentoril pregnant"]}'
    )
    exp = MultiQueryExpander(model)
    assert exp.expand("and in pregnancy?", []) == ["and in pregnancy?"]
    assert model.count("multi_query") == 0
    assert exp.expand(
        "and in pregnancy?", [("user", "What is Zentoril?"), ("assistant", "A fictional medicine.")]
    ) == [
        "Zentoril use in pregnancy",
        "Zentoril pregnant",
    ]


def test_graph_uses_standalone_rewrite_for_retrieval() -> None:
    seen: list[str] = []

    class SpyRetriever:
        def retrieve(self, query, k, filters=None, *, queries=None):
            seen.append(query)
            return []

    model = FakeChatModel(multi_query='{"standalone": "Zentoril pregnancy", "alternatives": []}')
    graph = build_rag_graph(SpyRetriever(), model, 0.2, expander=MultiQueryExpander(model))
    graph.invoke(
        {
            "question": "and in pregnancy?",
            "mode": AnswerMode.STANDARD,
            "k": 3,
            "history": [("user", "Zentoril?")],
        }
    )
    assert seen == ["Zentoril pregnancy"]


def _p(title: str, version: str, d: date, pid: str) -> Passage:
    return Passage(
        id=pid, text="threshold", source="s", publisher=PUB, title=title, version=version, publication_date=d
    )


def test_newest_version_preferred_and_conflict_noted() -> None:
    old = _p("Adult Hypertension Guideline v2 (SYNTHETIC)", "2.0", date(2019, 2, 1), "old")
    new = _p("Adult Hypertension Guideline v3 (SYNTHETIC)", "3.0", date(2024, 3, 1), "new")
    other = _p("Asthma Care (SYNTHETIC)", "1.0", date(2014, 5, 1), "other")
    out, notes = apply_version_preference([old, other, new])
    assert [p.id for p in out] == ["other", "new", "old"]
    assert next(p for p in out if p.id == "old").superseded
    assert not next(p for p in out if p.id == "new").superseded
    assert len(notes) == 1 and "may conflict" in notes[0] and "v3.0" in notes[0]
    assert 'status="SUPERSEDED' in format_passages(out)


def test_single_version_has_no_note() -> None:
    _, notes = apply_version_preference([_p("Guide v3 (SYNTHETIC)", "3", date(2024, 1, 1), "a")])
    assert notes == []


def test_chat_states_version_conflict(client_factory, token_factory) -> None:
    model = FakeChatModel(
        answer=cited(
            "Version 3 defines hypertension as 140/90 mmHg or higher {a}, while the older version used 150/95 mmHg {b}.",
            a="140/90",
            b="150/95",
        )
    )
    client, _ = client_factory(model, retrieval_backend="memory", retrieval_min_similarity=0.0)
    admin = {"Authorization": f"Bearer {token_factory('admin')}"}
    for name, version, d, text in [
        ("v3.md", "3.0", "2024-03-01", "Hypertension is defined as 140/90 mmHg or higher (SYNTHETIC)."),
        ("v2.md", "2.0", "2019-02-01", "Hypertension is defined as 150/95 mmHg or higher (SYNTHETIC)."),
    ]:
        res = client.post(
            "/api/admin/documents",
            headers=admin,
            data={
                "title": f"Adult Hypertension Guideline v{version[0]} (SYNTHETIC)",
                "publisher": PUB,
                "publication_date": d,
                "version": version,
            },
            files={"file": (name, text.encode())},
        )
        assert res.status_code == 200, res.text
    body = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {token_factory('user')}"},
        json={"question": "How is hypertension defined?"},
    ).json()
    assert body["kind"] == "answer", body
    assert any("more than one version" in w for w in body["warnings"])
    assert {c["superseded"] for c in body["citations"]} == {True, False}


def test_chat_filters_restrict_search(client_factory, token_factory) -> None:
    model = FakeChatModel(answer="NOT_COVERED")
    client, _ = client_factory(model, retrieval_backend="memory", retrieval_min_similarity=0.0)
    user = {"Authorization": f"Bearer {token_factory('user', sub='u1')}"}
    client.post(
        "/api/documents", headers=user, files={"file": ("n.txt", b"SYNTHETIC note on thirst and tiredness.")}
    )
    body = client.post(
        "/api/chat",
        headers=user,
        json={"question": "thirst and tiredness", "filters": {"trusted_only": True}},
    ).json()
    assert body["kind"] == "not_covered"  # the only matching doc is an upload, excluded by trusted_only
    assert model.count("answer") == 0


def test_filter_fields_cannot_disable_safety(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    res = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {token_factory('user')}"},
        json={"question": "I want to end my life", "filters": {"trusted_only": True, "safety": False}},
    )
    assert res.json()["kind"] == "emergency"


def test_filter_sql_is_parameterised_and_owner_scoped() -> None:
    params: dict = {}
    sql = filter_sql(
        SearchFilter(owner_id="u1", publishers=("A'; DROP TABLE x; --",), date_from=date(2020, 1, 1)), params
    )
    assert "DROP" not in sql  # values only ever travel as bind parameters
    assert ":owner_id" in sql and params["owner_id"] == "u1"
    assert params["publisher_0"].startswith("A'")
    assert params["date_from"] == "2020-01-01"
    trusted_only = filter_sql(SearchFilter(owner_id="u1", trusted_only=True), {})
    assert "owner_id" not in trusted_only
    anonymous = filter_sql(SearchFilter(), {})
    assert "owner_id" not in anonymous and "trusted" in anonymous
