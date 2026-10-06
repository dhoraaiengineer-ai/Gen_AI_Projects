"""Single-pass RAG as a LangGraph: retrieve -> generate (or -> no_documents)."""

import logging
from typing import Literal, TypedDict

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.rag.prompts import NO_DOCUMENTS_ANSWER, RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.rag.retriever import RetrievedChunk, Retriever, format_context, normalize_citations

logger = logging.getLogger(__name__)


class RAGState(TypedDict, total=False):
    question: str
    search_queries: list[str]  # extra phrasings to retrieve with (e.g. the user's original follow-up)
    top_k: int | None
    chunks: list[RetrievedChunk]
    answer: str
    model: str | None  # which model actually answered (differs from the primary after a fallback)


def build_rag_graph(retriever: Retriever, llm: Runnable[LanguageModelInput, BaseMessage]) -> CompiledStateGraph:
    def retrieve(state: RAGState) -> RAGState:
        queries = [state["question"], *state.get("search_queries", [])]
        chunks = retriever.retrieve(queries, state.get("top_k"))
        logger.info("retrieved chunks", extra={"count": len(chunks)})
        return {"chunks": chunks}

    def route_after_retrieve(state: RAGState) -> Literal["generate", "no_documents"]:
        return "generate" if state["chunks"] else "no_documents"

    def generate(state: RAGState) -> RAGState:
        prompt = RAG_USER_TEMPLATE.format(context=format_context(state["chunks"]), question=state["question"])
        response = llm.invoke([SystemMessage(RAG_SYSTEM_PROMPT), HumanMessage(prompt)])
        answer = normalize_citations(str(response.content).strip())
        return {"answer": answer, "model": response.response_metadata.get("model_name")}

    def no_documents(state: RAGState) -> RAGState:
        # Skip the LLM call entirely: nothing to ground an answer in.
        return {"answer": NO_DOCUMENTS_ANSWER}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("no_documents", no_documents)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges("retrieve", route_after_retrieve)
    graph.add_edge("generate", END)
    graph.add_edge("no_documents", END)
    return graph.compile()
