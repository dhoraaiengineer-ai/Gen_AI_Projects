from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.rag_graph import build_rag_graph
from app.agents.research_agent import build_research_agent
from app.rag.prompts import NO_DOCUMENTS_ANSWER
from app.rag.retriever import Retriever
from tests.conftest import fake_llm


def test_rag_graph_grounds_prompt_in_retrieved_documents(retriever: Retriever) -> None:
    retriever.ingest("Paris is the capital of France.", source="geo.md")
    llm = fake_llm("Paris [1].")

    state = build_rag_graph(retriever, llm).invoke({"question": "Capital of France?"})

    assert state["answer"] == "Paris [1]."
    assert [c.source for c in state["chunks"]] == ["geo.md"]
    prompt = llm.seen[0][-1].content
    assert '<document index="1" source="geo.md">' in prompt
    assert "Question: Capital of France?" in prompt


def test_rag_graph_skips_llm_when_nothing_retrieved(retriever: Retriever) -> None:
    llm = fake_llm()
    state = build_rag_graph(retriever, llm).invoke({"question": "Anything?"})
    assert state["answer"] == NO_DOCUMENTS_ANSWER
    assert llm.seen == []


def test_research_agent_calls_search_tool_then_answers(retriever: Retriever) -> None:
    retriever.ingest("Paris is the capital of France.", source="geo.md")
    llm = fake_llm(
        AIMessage(
            "", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "capital of France"}, "id": "c1"}]
        ),
        "Paris (geo.md).",
    )

    state = build_research_agent(retriever, llm).invoke({"messages": [HumanMessage("Capital of France?")]})

    tool_msg = next(m for m in state["messages"] if isinstance(m, ToolMessage))
    assert tool_msg.tool_call_id == "c1"
    assert "Paris is the capital of France." in tool_msg.content
    assert state["messages"][-1].content == "Paris (geo.md)."
