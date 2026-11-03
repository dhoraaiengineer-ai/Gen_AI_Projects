"""Real query + Recall@5 ground truth for the golden-path demo document.

Part A.1 (12-Jul-2026) made Recall@5 a real measurement instead of the neutral
0.5 placeholder `ragas_service.compute_extended_metrics` returns whenever
`relevant_ids=None`. P0.5-1 (12-Jul-2026) closes the gap that made every live
run invalid for that purpose: `POST /evaluate` always dispatched with
`raw_query=""`, so Query Rewriter/Builder/Evaluator had nothing to actually
retrieve against, faithfulness hard-blocked at 0.0 on every run, and
Observer/Diagnoser/Improver were never reached.

Ground truth here pairs each question with its own keyword group, not a
merged pool -- `resolve_relevant_ids` scores recall against the specific
question that was actually asked, not "any of 5 unrelated topics." Content
genuinely drawn from the paper, not fabricated placeholders. Matching is by
chunk content (case-insensitive keyword containment), not chunk_id: chunk_id
is deterministic per (org, source, strategy, page, index) as of P0.5-2, but a
static ID list would still break if chunking parameters ever change --
content matching is stable across any re-ingestion of the same document.

Scoped to this one demo document only. For any other pipeline/document,
`resolve_relevant_ids` returns None and Recall@5 stays the 0.5 placeholder --
a real, documented limitation, not a general ground-truth management feature.
"""

from __future__ import annotations

from typing import NamedTuple

from app.services.vector_service import VectorService

# Matches any chunk whose source_uri contains this substring (case-insensitive).
GOLDEN_PATH_DOCUMENT_MARKER = "attention-is-all-you-need"


class GoldenPathQuestion(NamedTuple):
    question_id: str
    query: str
    keyword_group: list[str]


# Each question's keyword_group: a chunk counts as relevant to that question
# if its text contains ALL keywords in the group (case-insensitive).
_GOLDEN_PATH_QUESTIONS: list[GoldenPathQuestion] = [
    GoldenPathQuestion(
        question_id="gp-1",
        query="What is scaled dot-product attention?",
        keyword_group=["scaled dot-product attention"],
    ),
    GoldenPathQuestion(
        question_id="gp-2",
        query="How does multi-head attention work in the Transformer?",
        keyword_group=["multi-head attention"],
    ),
    GoldenPathQuestion(
        question_id="gp-3",
        query="How does the Transformer encode positional information without recurrence?",
        keyword_group=["positional encoding"],
    ),
    GoldenPathQuestion(
        question_id="gp-4",
        query="Why does the Transformer replace recurrence and convolutions with self-attention?",
        keyword_group=["self-attention", "recurrence"],
    ),
    GoldenPathQuestion(
        question_id="gp-5",
        query="What dataset was used to train the WMT 2014 translation model?",
        keyword_group=["wmt 2014"],
    ),
]


def _chunk_matches_group(chunk_text: str, keywords: list[str]) -> bool:
    lowered = chunk_text.lower()
    return all(kw.lower() in lowered for kw in keywords)


def default_golden_path_question() -> GoldenPathQuestion:
    """The representative question used when a golden-path document is detected
    and the caller didn't supply its own `query`. Always the same question for
    a given pipeline, so repeated dataset-driven runs are comparable."""
    return _GOLDEN_PATH_QUESTIONS[0]


def _keyword_group_for_query(query: str) -> list[str] | None:
    """Return the keyword group for a query that exactly matches a known
    golden-path question, or None if the query isn't one of them (e.g. a real
    user-typed query, or a query against a non-golden-path document)."""
    for q in _GOLDEN_PATH_QUESTIONS:
        if q.query == query:
            return q.keyword_group
    return None


async def is_golden_path_document(
    *,
    vector_service: VectorService,
    pipeline_id: str,
    pipeline_version: str,
    organization_id: str,
) -> bool:
    """Whether this pipeline's ingested chunks come from the golden-path demo document."""
    chunks = await vector_service.list_all_chunks(
        pipeline_id=pipeline_id,
        version=pipeline_version,
        organization_id=organization_id,
    )
    return any(
        GOLDEN_PATH_DOCUMENT_MARKER in (c.get("source_uri") or "").lower()
        for c in chunks
    )


async def resolve_relevant_ids(
    *,
    vector_service: VectorService,
    pipeline_id: str,
    pipeline_version: str,
    organization_id: str,
    query: str,
) -> list[str] | None:
    """Return real chunk_ids relevant to `query`, or None if no ground truth exists for it.

    Returns None (not an empty list) whenever this query isn't a recognized
    golden-path question, or the pipeline's chunks aren't the golden-path
    document -- callers must treat None as "no ground truth available" (the
    existing placeholder behavior), not "zero relevant chunks found" (which
    would incorrectly score recall as 0).
    """
    keyword_group = _keyword_group_for_query(query)
    if keyword_group is None:
        return None

    chunks = await vector_service.list_all_chunks(
        pipeline_id=pipeline_id,
        version=pipeline_version,
        organization_id=organization_id,
    )
    if not chunks:
        return None

    is_golden_path = any(
        GOLDEN_PATH_DOCUMENT_MARKER in (c.get("source_uri") or "").lower()
        for c in chunks
    )
    if not is_golden_path:
        return None

    return [
        chunk["chunk_id"]
        for chunk in chunks
        if _chunk_matches_group(chunk.get("chunk_text") or "", keyword_group)
    ]
