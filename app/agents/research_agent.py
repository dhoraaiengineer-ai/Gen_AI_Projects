"""Tool-calling research agent as a LangGraph: the model searches as many times as it needs.

Use this over the single-pass RAG graph for multi-part questions, comparisons, or
"find everything about X" tasks where one retrieval isn't enough.
"""

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool, tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.rag.prompts import AGENT_SYSTEM_PROMPT
from app.rag.retriever import Retriever, format_context


def build_search_tool(retriever: Retriever) -> BaseTool:
    @tool
    def search_knowledge_base(query: str, top_k: int = 4) -> str:
        """Semantic search over the ingested documents. Returns the most relevant passages
        with their source names. Use short, specific queries; search again with different
        wording if the results are thin. top_k is the number of passages (1-10)."""
        chunks = retriever.retrieve(query, max(1, min(top_k, 10)))
        return format_context(chunks) if chunks else "No matching passages."

    return search_knowledge_base


def build_research_agent(
    retriever: Retriever,
    llm: BaseChatModel,
    fallback: BaseChatModel | None = None,
    fallback_exceptions: Sequence[type[BaseException]] = (Exception,),
) -> CompiledStateGraph:
    tools = [build_search_tool(retriever)]
    # Tools must be bound on each model before chaining fallbacks (RunnableWithFallbacks has no bind_tools).
    llm_with_tools = llm.bind_tools(tools)
    if fallback is not None:
        llm_with_tools = llm_with_tools.with_fallbacks(
            [fallback.bind_tools(tools)], exceptions_to_handle=tuple(fallback_exceptions)
        )

    def agent(state: MessagesState) -> MessagesState:
        response = llm_with_tools.invoke([SystemMessage(AGENT_SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    graph.add_edge("tools", "agent")
    return graph.compile()
