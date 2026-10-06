from typing import Any

import httpx
import openai
from langchain_core.messages import AIMessage, BaseMessage

from app.core.metrics import LLM_FALLBACKS, FallbackCounter
from tests.conftest import AppHarness, FakeChatModel, fake_llm

INGEST = {"documents": [{"text": "Paris is the capital of France.", "source": "geo.md"}]}


class FailingChatModel(FakeChatModel):
    """Primary model that fails the way EURI does when a model's daily quota is used up."""

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> BaseMessage:
        request = httpx.Request("POST", "https://llm.test/chat/completions")
        raise openai.RateLimitError("daily quota", response=httpx.Response(429, request=request), body=None)


def fallback_model(name: str, *responses: AIMessage) -> FakeChatModel:
    llm = fake_llm(*responses)
    llm.callbacks = [FallbackCounter(name)]
    return llm


def failing_client(harness: AppHarness):
    client = harness.client()
    harness.llm.__class__ = FailingChatModel  # swap before the app starts and wires the graphs
    return client


def test_query_falls_back_when_primary_fails(harness: AppHarness) -> None:
    answer = AIMessage("Paris [1].", response_metadata={"model_name": "gemini-2.0-flash"})
    harness.fallback_llm = fallback_model("gemini-2.0-flash", answer)
    before = LLM_FALLBACKS.labels("gemini-2.0-flash")._value.get()

    with failing_client(harness) as c:
        c.post("/api/v1/ingest", json=INGEST)
        r = c.post("/api/v1/query", json={"question": "Capital of France?"})

    assert r.status_code == 200
    assert r.json()["answer"] == "Paris [1]."
    assert r.json()["model"] == "gemini-2.0-flash"  # reports the model that actually answered
    assert LLM_FALLBACKS.labels("gemini-2.0-flash")._value.get() == before + 1


def test_agent_uses_its_own_tool_capable_fallback(harness: AppHarness) -> None:
    tool_call = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "France"}, "id": "c1"}])
    final = AIMessage("Paris (geo.md).", response_metadata={"model_name": "gpt-4o-mini"})
    harness.fallback_llm = fallback_model("gemini-2.0-flash")  # must NOT be used by the agent
    harness.agent_fallback_llm = fallback_model("gpt-4o-mini", tool_call, final)

    with failing_client(harness) as c:
        c.post("/api/v1/ingest", json=INGEST)
        r = c.post("/api/v1/agent", json={"task": "Capital of France?"})

    assert r.json() == {"answer": "Paris (geo.md).", "tool_calls": 1, "model": "gpt-4o-mini"}
    assert harness.fallback_llm.seen == []


def test_without_fallback_the_error_surfaces_as_429(harness: AppHarness) -> None:
    with failing_client(harness) as c:
        c.post("/api/v1/ingest", json=INGEST)
        assert c.post("/api/v1/query", json={"question": "Capital?"}).status_code == 429
