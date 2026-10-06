import json

import pytest
from langchain_core.embeddings import Embeddings

from app.agents.rag_graph import build_rag_graph
from app.rag.evaluation import Evaluator
from app.rag.golden import GoldenItem
from app.rag.ragas_metrics import RagasJudge, average_precision
from app.rag.retriever import Retriever
from tests.conftest import AppHarness, fake_llm


class SameEmbeddings(Embeddings):
    """Every text maps to the same vector, so cosine similarity is always 1."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


def _reply(data: object) -> str:
    return "```json\n" + json.dumps(data) + "\n```"


def test_faithfulness_is_supported_claims_over_all_claims() -> None:
    judge = RagasJudge(fake_llm(_reply({"claims": [{"supported": True}, {"supported": True}, {"supported": False}]})))
    assert judge.faithfulness("answer", ["ctx"]) == pytest.approx(2 / 3)


def test_faithfulness_without_claims_is_not_applicable() -> None:
    assert RagasJudge(fake_llm(_reply({"claims": []}))).faithfulness("I don't know.", ["ctx"]) is None


def test_answer_relevancy_uses_embedding_similarity_and_penalises_noncommittal() -> None:
    relevant = RagasJudge(fake_llm(_reply({"questions": ["a?", "b?"], "noncommittal": False})), SameEmbeddings())
    assert relevant.answer_relevancy("q?", "answer") == pytest.approx(1.0)
    evasive = RagasJudge(fake_llm(_reply({"questions": ["a?"], "noncommittal": True})), SameEmbeddings())
    assert evasive.answer_relevancy("q?", "I don't know") == 0.0


def test_context_precision_rewards_useful_contexts_ranked_first() -> None:
    assert average_precision([True, False, False]) == 1.0
    assert average_precision([False, False, True]) == pytest.approx(1 / 3)
    assert average_precision([False, False]) == 0.0
    judge = RagasJudge(fake_llm(_reply({"useful": [2]})))
    assert judge.context_precision("q", "ref", ["a", "b"]) == pytest.approx(0.5)


def test_context_recall_is_attributed_statements_over_all() -> None:
    judge = RagasJudge(fake_llm(_reply({"statements": [{"attributed": True}, {"attributed": False}]})))
    assert judge.context_recall("ref", ["ctx"]) == 0.5


def test_a_broken_judge_reply_gives_none_not_a_crash() -> None:
    scores = RagasJudge(fake_llm("I refuse to answer in JSON")).score("q", "a", ["c"], "ref", ["context_recall"])
    assert scores == {"context_recall": None}


def test_evaluator_reports_ragas_metrics_and_grounding(retriever: Retriever) -> None:
    retriever.ingest_text("Paris is the capital of France.", source="geo.md")
    item = GoldenItem.create("geo.md", "What is the capital of France?", "Paris", "capital of France", None, "manual")
    llm = fake_llm(
        "Paris [1].",  # the answer
        '{"correct": true, "reason": "same"}',  # LLM-as-judge correctness
        _reply({"claims": [{"supported": True}]}),  # faithfulness
        _reply({"useful": [1]}),  # context precision
        _reply({"statements": [{"attributed": True}]}),  # context recall
    )
    evaluator = Evaluator(retriever, build_rag_graph(retriever, llm), llm, RagasJudge(llm))
    report = evaluator.run([item], top_k=1, metrics=["faithfulness", "context_precision", "context_recall"])

    [result] = report.items
    assert result.ragas == {"faithfulness": 1.0, "context_precision": 1.0, "context_recall": 1.0}
    assert result.grounded is True
    assert report.ragas_mean("faithfulness") == 1.0
    assert report.ragas_mean("answer_relevancy") is None  # not requested


def test_eval_api_returns_ragas_metrics(harness: AppHarness) -> None:
    item = {"source": "geo.md", "question": "What is the capital of France?", "answer": "Paris", "evidence": "capital"}
    responses = ["Paris [1].", '{"correct": true, "reason": "ok"}', _reply({"claims": [{"supported": True}]})]
    with harness.client(*responses) as c:
        c.post("/api/v1/ingest", json={"documents": [{"text": "Paris is the capital of France.", "source": "geo.md"}]})
        c.post("/api/v1/golden", json={"items": [item]})
        report = c.post("/api/v1/eval", json={"top_k": 1, "metrics": ["faithfulness"]}).json()

    assert report["faithfulness"] == 1.0
    assert report["answer_accuracy"] == 1.0
    assert report["grounded_rate"] == 1.0
    assert report["items"][0]["faithfulness"] == 1.0
    assert report["context_recall"] is None
