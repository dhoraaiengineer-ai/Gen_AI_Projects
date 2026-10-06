from langchain_core.documents import Document

from app.agents.rag_graph import build_rag_graph
from app.rag.evaluation import Evaluator, cited_chunks, parse_verdict
from app.rag.golden import GoldenItem
from app.rag.retriever import RetrievedChunk, Retriever
from tests.conftest import fake_llm

PARIS = GoldenItem.create("geo.md", "What is the capital of France?", "Paris", "capital of France", None, "manual")
MISSING = GoldenItem.create("geo.md", "What is the capital of Peru?", "Lima", "Lima is the capital", None, "manual")


def _evaluator(retriever: Retriever, *responses: str) -> Evaluator:
    llm = fake_llm(*responses)
    return Evaluator(retriever, build_rag_graph(retriever, llm), llm)


def test_retrieval_only_metrics(retriever: Retriever) -> None:
    retriever.ingest_text("Paris is the capital of France.", source="geo.md")
    report = _evaluator(retriever).run([PARIS, MISSING], top_k=2, judge=False)

    paris, missing = report.items
    assert paris.evidence_rank == 1 and paris.source_hit
    assert missing.evidence_rank is None and missing.source_hit  # right document, evidence not in it
    assert report.evidence_hit_rate == 0.5
    assert report.source_hit_rate == 1.0
    assert report.mrr == 0.5
    assert report.answer_accuracy is None and report.citation_accuracy is None


def test_judged_run_grades_answers_and_citations(retriever: Retriever) -> None:
    retriever.ingest_text("Paris is the capital of France.", source="geo.md")
    evaluator = _evaluator(retriever, "Paris [1].", '{"correct": true, "reason": "matches"}')
    [result] = evaluator.run([PARIS], top_k=1).items

    assert result.answer == "Paris [1]."
    assert result.correct is True
    assert result.judge_reason == "matches"
    assert result.cited_expected_source is True


def test_answer_without_citation_scores_zero_citation_accuracy(retriever: Retriever) -> None:
    retriever.ingest_text("Paris is the capital of France.", source="geo.md")
    evaluator = _evaluator(retriever, "Paris.", '{"correct": true, "reason": "ok"}')
    report = evaluator.run([PARIS], top_k=1)
    assert report.answer_accuracy == 1.0
    assert report.citation_accuracy == 0.0


def test_empty_golden_set_gives_empty_report(retriever: Retriever) -> None:
    report = _evaluator(retriever).run([], judge=False)
    assert report.items == [] and report.mrr is None and report.evidence_hit_rate is None


def test_cited_chunks_ignores_out_of_range_indexes() -> None:
    chunks = [RetrievedChunk(Document("a", metadata={"source": "x"}), 1.0)]
    assert cited_chunks("See [1] and [7].", chunks) == chunks


def test_parse_verdict_tolerates_noise() -> None:
    assert parse_verdict('Sure! {"correct": false, "reason": "wrong year"}') == (False, "wrong year")
    assert parse_verdict("no json") == (None, "")
    assert parse_verdict('{"correct": "yes"}') == (None, "")
