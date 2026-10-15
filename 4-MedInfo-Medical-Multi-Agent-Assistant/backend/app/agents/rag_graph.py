"""LangGraph RAG graph: retrieve -> generate. Safety steps run around it in app/rag/service.py,
so no path through the graph can skip them."""

from __future__ import annotations

import logging
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.metrics import TOKEN_BUDGET_EVENTS
from app.rag.interfaces import ChatModel, Passage, Retriever, SearchFilter
from app.rag.prompts import NOT_COVERED_TOKEN, AnswerMode, system_prompt, user_prompt

logger = logging.getLogger(__name__)


class QueryExpander(Protocol):
    def expand(self, question: str, history: list[tuple[str, str]]) -> list[str]: ...


class RagState(TypedDict, total=False):
    question: str
    history: list[tuple[str, str]]
    queries: list[str]
    mode: AnswerMode
    k: int
    filters: SearchFilter
    passages: list[Passage]
    raw_answer: str
    not_covered: bool


def fit_passages(model: ChatModel, system: str, question: str, passages: list[Passage]) -> list[Passage]:
    """Token budget: drop the lowest-ranked passages until the prompt fits the gateway's input budget for
    the answer task (keeps at least one; if even that does not fit, the gateway refuses the call)."""
    fits = getattr(model, "fits", None)
    if fits is None:
        return passages
    kept = list(passages)
    while len(kept) > 1 and not fits(system, user_prompt(question, kept)):
        kept.pop()
    if len(kept) < len(passages):
        TOKEN_BUDGET_EVENTS.labels("answer", "passages_trimmed").inc()
        logger.info("passages trimmed to the token budget", extra={"kept": len(kept), "of": len(passages)})
    return kept


def build_rag_graph(
    retriever: Retriever, model: ChatModel, temperature: float, expander: QueryExpander | None = None
) -> Any:
    def rewrite(state: RagState) -> RagState:
        history = state.get("history") or []
        if expander is None or not history:
            return {"queries": [state["question"]]}
        queries = expander.expand(state["question"], history)
        logger.info("follow-up rewritten", extra={"queries": len(queries)})
        return {"queries": queries}

    def retrieve(state: RagState) -> RagState:
        queries = state.get("queries") or [state["question"]]
        # Retrieval uses the standalone rewrite (queries[0]); the answer still sees the user's own words.
        passages = retriever.retrieve(queries[0], state.get("k", 5), state.get("filters"), queries=queries)
        logger.info("retrieved", extra={"passages": len(passages)})
        return {"passages": passages}

    def generate(state: RagState) -> RagState:
        passages = state.get("passages") or []
        if not passages:
            # No sources -> never answer from model memory.
            return {"raw_answer": "", "not_covered": True}
        system = system_prompt(state["mode"])
        passages = fit_passages(model, system, state["question"], passages)
        raw = model.complete(system, user_prompt(state["question"], passages), temperature=temperature)
        not_covered = raw.strip().strip(".").upper() == NOT_COVERED_TOKEN
        # The (possibly trimmed) passages are returned so the verifier checks exactly what the model saw.
        return {"raw_answer": raw, "not_covered": not_covered, "passages": passages}

    graph = StateGraph(RagState)
    graph.add_node("rewrite", rewrite)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
