"""Stage 5: golden set integrity, retrieval metrics, judge robustness, clinician review workflow, eval runner."""

from __future__ import annotations

import pytest
import yaml

from app.config import PROJECT_ROOT
from app.core.audit import AuditLogger
from app.rag.chunking import Chunker
from app.rag.evaluation import (
    EvalJudge,
    GoldenSet,
    ItemResult,
    context_precision,
    evidence_rank,
    hit_rate,
    mrr,
    summarise,
)
from app.rag.ingest import IngestService, Provenance, TrustedSources
from app.rag.interfaces import Passage, SearchFilter
from app.rag.loaders import load_document
from app.rag.memory_store import InMemoryRegistry, InMemoryVectorIndex
from app.rag.retrieval import HybridRetriever
from app.safety.text import normalise
from tests.fakes import FakeChatModel, FakeEmbedder, FakeOcr

CORPUS = PROJECT_ROOT / "data" / "synthetic" / "corpus"
GOLDEN = GoldenSet.load(PROJECT_ROOT / "evals" / "golden.yaml")
MANIFEST = yaml.safe_load((CORPUS / "manifest.yaml").read_text(encoding="utf-8"))["documents"]


@pytest.mark.parametrize("item", [i for i in GOLDEN.items if not i.needs_ocr], ids=lambda i: i.id)
def test_golden_evidence_quote_is_verbatim_in_its_document(item) -> None:
    text = "\n".join(s.text for s in load_document(item.doc, (CORPUS / item.doc).read_bytes(), None))
    assert normalise(item.evidence) in normalise(text), item.id


@pytest.mark.slow
@pytest.mark.parametrize("item", [i for i in GOLDEN.items if i.needs_ocr], ids=lambda i: i.id)
def test_golden_evidence_in_scanned_document(item) -> None:
    from app.rag.ocr import RapidOcrEngine

    text = "\n".join(
        s.text for s in load_document(item.doc, (CORPUS / item.doc).read_bytes(), RapidOcrEngine())
    )
    assert normalise(item.evidence) in normalise(text)


def test_golden_set_shape() -> None:
    assert len(GOLDEN.items) >= 12 and len({i.id for i in GOLDEN.items}) == len(GOLDEN.items)
    assert all(i.doc in MANIFEST and i.facts for i in GOLDEN.items)
    assert len(GOLDEN.out_of_corpus) >= 3


def test_metric_maths() -> None:
    assert hit_rate([1, 3, None, 6], k=5) == 0.5
    assert mrr([1, 2, None, 4]) == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)
    assert context_precision([True, False, True]) == pytest.approx((1 / 1 + 2 / 3) / 2)
    assert context_precision([False, False]) == 0.0
    p = [
        Passage(id="a", text="x", source="s", publisher="p", title="t"),
        Passage(id="b", text="The usual  STARTING dose is 10 mg.", source="s", publisher="p", title="t"),
    ]
    assert evidence_rank("the usual starting dose", p) == 2
    s = summarise(
        [
            ItemResult("1", "q", "info", 1, metrics={"correctness": 1.0}),
            ItemResult("2", "q", "info", None, metrics={"correctness": 0.0}),
        ],
        k=5,
    )
    assert s["evidence_hit_rate"] == 0.5 and s["correctness"] == 0.5


def test_offline_retrieval_quality_on_synthetic_golden_set() -> None:
    """Regression guard for hybrid retrieval (fake embeddings + keyword search; no model calls)."""
    index, registry, emb = InMemoryVectorIndex(), InMemoryRegistry(), FakeEmbedder(dimensions=256)
    ingest = IngestService(
        registry=registry,
        index=index,
        embedder=emb,
        chunker=Chunker("recursive"),
        ocr=FakeOcr(),
        trusted_sources=TrustedSources.load(),
        trusted_collection="t",
        user_collection="u",
        max_bytes=10**7,
        audit=AuditLogger(False),
    )
    for name, meta in MANIFEST.items():
        ingest.ingest_trusted(name, (CORPUS / name).read_bytes(), Provenance(**meta), actor_id="eval")
    retriever = HybridRetriever(
        index=index,
        embedder=emb,
        registry=registry,
        trusted_collection="t",
        user_collection="u",
        min_similarity=0.0,
    )
    items = [i for i in GOLDEN.items if not i.needs_ocr]
    ranks = [evidence_rank(i.evidence, retriever.retrieve(i.question, 5, SearchFilter())) for i in items]
    assert hit_rate(ranks, 5) >= 0.9, list(zip([i.id for i in items], ranks, strict=True))


def test_judge_parses_and_fails_closed() -> None:
    good = FakeChatModel(answer='{"correctness": 0.9, "citation_accuracy": 1.2, "reason": "ok"}')
    m = EvalJudge(good).correctness("q", "a [1].", ["fact"], [])
    assert m == {"correctness": 0.9, "citation_accuracy": 1.0}  # clipped to [0, 1]
    bad = FakeChatModel(answer="not json")
    assert EvalJudge(bad).correctness("q", "a", ["f"], []) == {"correctness": 0.0, "citation_accuracy": 0.0}
    assert EvalJudge(bad).context_recall(["f"], ["c"]) == 0.0
    assert EvalJudge(FakeChatModel(answer='{"claims": 4, "supported": 3}')).faithfulness("x", ["c"]) == 0.75
    assert EvalJudge(FakeChatModel(answer='{"relevant": [true]}')).context_relevance("q", ["a", "b"]) == [
        True,
        False,
    ]


# ---- clinician review workflow ------------------------------------------------------------------------
def test_review_workflow(client_factory, token_factory) -> None:
    from tests.fakes import cited

    model = FakeChatModel(answer=cited("Hypertension often causes no symptoms {a}.", a="no symptoms"))
    client, _ = client_factory(model, review_sample_rate=1.0)
    user = {"Authorization": f"Bearer {token_factory('user')}"}
    clin = {"Authorization": f"Bearer {token_factory('clinician', sub='clin-1')}"}
    admin = {"Authorization": f"Bearer {token_factory('admin')}"}
    client.post(
        "/api/chat", headers=user, json={"question": "My name is Priya Sharma. What is hypertension?"}
    )

    assert client.get("/api/review/queue", headers=user).status_code == 403
    queue = client.get("/api/review/queue", headers=clin).json()
    assert len(queue) == 1 and "Priya Sharma" not in str(queue)  # sampled text is redacted
    item = queue[0]["id"]
    assert client.post(f"/api/review/{item}", headers=clin, json={"verdict": "great"}).status_code == 422
    res = client.post(
        f"/api/review/{item}", headers=clin, json={"verdict": "minor_issue", "notes": "wording"}
    )
    assert res.json()["status"] == "reviewed"
    assert client.get("/api/review/queue", headers=clin).json() == []
    assert client.get("/api/review/summary", headers=clin).json()["minor_issue"] == 1
    assert client.get("/api/admin/review/export?format=csv", headers=clin).status_code == 403
    csv_text = client.get("/api/admin/review/export?format=csv", headers=admin).text
    assert "minor_issue" in csv_text and "clin-1" in csv_text
    assert (
        client.post("/api/review/does-not-exist", headers=clin, json={"verdict": "unsafe"}).status_code == 404
    )


def test_refusals_and_emergencies_are_not_sampled(client_factory, auth_header, token_factory) -> None:
    client, _ = client_factory(FakeChatModel(answer="NOT_COVERED"), review_sample_rate=1.0)
    client.post("/api/chat", headers=auth_header, json={"question": "I have crushing chest pain"})
    client.post("/api/chat", headers=auth_header, json={"question": "Can I double my dose of Zentoril?"})
    clin = {"Authorization": f"Bearer {token_factory('clinician')}"}
    assert client.get("/api/review/queue", headers=clin).json() == []


def test_eval_runner_dry_run_makes_no_calls(monkeypatch, capsys) -> None:
    import evals.run_eval as run_eval

    def boom(*a, **k):
        raise AssertionError("no container/model may be built in a dry run")

    monkeypatch.setattr(run_eval, "build_container", boom)
    monkeypatch.setattr(run_eval, "build_chat_model", boom)
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--retrieval", "--answers", "--safety"])
    assert run_eval.main() == 0
    out = capsys.readouterr().out
    assert "Estimated live calls" in out and "Dry run only" in out


def test_judge_waits_out_quota_errors_then_scores() -> None:
    from app.core.errors import ProviderQuotaError
    from app.rag.evaluation import EvalJudge

    class Flaky:
        name = "fake:flaky"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, system, user, *, temperature, max_tokens=None):
            self.calls += 1
            if self.calls == 1:
                raise ProviderQuotaError(retry_after=2)
            return '{"relevancy": 1}'

    slept: list[float] = []
    judge = EvalJudge(Flaky(), sleep=slept.append)
    assert judge.answer_relevancy("q", "a") == 1.0
    assert slept == [2.0] and judge.errors == 0


def test_judge_failures_are_counted_and_score_zero() -> None:
    from app.core.errors import ProviderQuotaError
    from app.rag.evaluation import EvalJudge

    class AlwaysQuota:
        name = "fake:quota"

        def complete(self, system, user, *, temperature, max_tokens=None):
            raise ProviderQuotaError()

    judge = EvalJudge(AlwaysQuota(), quota_retries=2, sleep=lambda s: None)
    assert judge.answer_relevancy("q", "a") == 0.0
    assert judge.errors == 1
