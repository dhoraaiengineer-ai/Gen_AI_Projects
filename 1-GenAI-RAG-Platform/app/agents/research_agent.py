"""Tool-calling research agent as a LangGraph: the model searches as many times as it needs.

Use this over the single-pass RAG graph for multi-part questions, comparisons, or
"find everything about X" tasks where one retrieval isn't enough.

Tools: `search_knowledge_base` (always) and `search_web` (only when a web search provider is configured).
"""

import logging
from collections.abc import Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.core.metrics import WEB_SEARCHES
from app.rag.prompts import AGENT_SYSTEM_PROMPT, AGENT_WEB_SEARCH_PROMPT
from app.rag.retriever import Retriever, format_context
from app.rag.websearch import WebResult, WebSearch, WebSearchError, format_web_results

logger = logging.getLogger(__name__)

WEB_TOOL_NAME = "search_web"


def build_search_tool(retriever: Retriever) -> BaseTool:
    @tool
    def search_knowledge_base(query: str, config: RunnableConfig, top_k: int = 4) -> str:
        """Semantic search over the ingested documents. Returns the most relevant passages
        with their source names. Use short, specific queries; search again with different
        wording if the results are thin. top_k is the number of passages (1-10)."""
        # No LLM re-ranking here: the agent judges results itself, and it may search several times.
        filters = (config.get("configurable") or {}).get("filters")  # the request's metadata filter
        chunks = retriever.retrieve(query, max(1, min(top_k, 10)), rerank=False, filters=filters)
        return format_context(chunks) if chunks else "No matching passages."

    return search_knowledge_base


def build_web_search_tool(
    web_search: WebSearch, max_results: int, content_guard: Callable[[str], str] | None = None
) -> BaseTool:
    @tool(WEB_TOOL_NAME, response_format="content_and_artifact")
    def search_web(query: str) -> tuple[str, list[str]]:
        """Search the public web. Use it only when the knowledge base doesn't cover the question, or the
        question needs recent or external information. Returns page snippets with their URLs."""
        try:
            results = web_search.search(query, max_results)
        except WebSearchError as exc:
            WEB_SEARCHES.labels("error").inc()
            logger.warning("web search failed", extra={"error": str(exc)})
            return f"Web search is unavailable right now ({exc}). Answer from the knowledge base.", []
        WEB_SEARCHES.labels("ok" if results else "empty").inc()
        if not results:
            return "No web results.", []
        if content_guard is not None:  # web pages are untrusted: mark injected instructions, redact secrets
            results = [WebResult(r.title, r.url, content_guard(r.content), r.score) for r in results]
        return format_web_results(results), [r.url for r in results]  # artifact: URLs for the API response

    return search_web


def as_model_list(models: BaseChatModel | Sequence[BaseChatModel] | None) -> list[BaseChatModel]:
    if models is None:
        return []
    return [models] if isinstance(models, BaseChatModel) else list(models)


def build_research_agent(
    retriever: Retriever,
    llm: BaseChatModel,
    fallback: BaseChatModel | Sequence[BaseChatModel] | None = None,
    fallback_exceptions: Sequence[type[BaseException]] = (Exception,),
    web_search: WebSearch | None = None,
    web_max_results: int = 5,
    content_guard: Callable[[str], str] | None = None,
) -> CompiledStateGraph:
    tools = [build_search_tool(retriever)]
    system_prompt = AGENT_SYSTEM_PROMPT
    if web_search is not None:
        tools.append(build_web_search_tool(web_search, web_max_results, content_guard))
        system_prompt += "\n\n" + AGENT_WEB_SEARCH_PROMPT
    # Tools must be bound on each model before chaining fallbacks (RunnableWithFallbacks has no bind_tools).
    llm_with_tools = llm.bind_tools(tools)
    fallbacks = as_model_list(fallback)
    if fallbacks:
        llm_with_tools = llm_with_tools.with_fallbacks(
            [f.bind_tools(tools) for f in fallbacks], exceptions_to_handle=tuple(fallback_exceptions)
        )

    def agent(state: MessagesState) -> MessagesState:
        response = llm_with_tools.invoke([SystemMessage(system_prompt), *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    graph.add_edge("tools", "agent")
    return graph.compile()
