"""Use cases the API exposes. Routes call this; this calls the graphs and retriever."""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from app.core.metrics import AGENT_TOOL_CALLS, CHUNKS_INGESTED, DOCUMENTS_RETRIEVED
from app.models.schemas import AgentResponse, DocumentIn, IngestResponse, QueryResponse, SourceChunk
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        retriever: Retriever,
        rag_graph: CompiledStateGraph,
        research_agent: CompiledStateGraph,
        model_name: str,
        agent_max_iterations: int,
    ):
        self.retriever = retriever
        self.rag_graph = rag_graph
        self.research_agent = research_agent
        self.model_name = model_name
        self.agent_max_iterations = agent_max_iterations

    def ingest(self, documents: list[DocumentIn]) -> IngestResponse:
        total = sum(self.retriever.ingest(d.text, source=d.source, metadata=d.metadata) for d in documents)
        CHUNKS_INGESTED.inc(total)
        return IngestResponse(documents=len(documents), chunks=total)

    def query(self, question: str, top_k: int | None = None) -> QueryResponse:
        state = self.rag_graph.invoke({"question": question, "top_k": top_k})
        chunks = state.get("chunks", [])
        DOCUMENTS_RETRIEVED.observe(len(chunks))
        sources = [SourceChunk(source=c.source, text=c.document.page_content, score=round(c.score, 4)) for c in chunks]
        return QueryResponse(answer=state["answer"], sources=sources, model=state.get("model") or self.model_name)

    def run_agent(self, task: str) -> AgentResponse:
        # Each iteration is an agent step plus a tools step.
        config = {"recursion_limit": 2 * self.agent_max_iterations + 1}
        try:
            state = self.research_agent.invoke({"messages": [HumanMessage(task)]}, config=config)
        except GraphRecursionError:
            logger.warning("agent hit iteration limit", extra={"limit": self.agent_max_iterations})
            return AgentResponse(
                answer="The agent hit its search limit before finishing. Try a narrower question.",
                tool_calls=self.agent_max_iterations,
                model=self.model_name,
            )

        messages = state["messages"]
        tool_calls = sum(len(m.tool_calls) for m in messages if isinstance(m, AIMessage))
        AGENT_TOOL_CALLS.observe(tool_calls)
        final = messages[-1]
        answer = str(final.content).strip() if isinstance(final, AIMessage) else ""
        answered_by = final.response_metadata.get("model_name") if isinstance(final, AIMessage) else None
        return AgentResponse(
            answer=answer or "The agent stopped without producing an answer.",
            tool_calls=tool_calls,
            model=answered_by or self.model_name,
        )
