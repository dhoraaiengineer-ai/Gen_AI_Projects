import httpx
import pytest
from langchain_core.messages import AIMessage

from app.agents.research_agent import build_web_search_tool
from app.config import Settings
from app.rag import providers
from app.rag.providers import TavilyWebSearch
from app.rag.websearch import WebResult, WebSearchError, format_web_results
from tests.conftest import AppHarness


class FakeWebSearch:
    def __init__(self, results: list[WebResult] | None = None, error: str | None = None):
        self.results = results or []
        self.error = error
        self.queries: list[str] = []

    def search(self, query: str, max_results: int) -> list[WebResult]:
        self.queries.append(query)
        if self.error:
            raise WebSearchError(self.error)
        return self.results[:max_results]


RESULT = WebResult("IIE journal", "https://journal.example/issn", "ISSN 0970-2555, published monthly.", 0.9)


def _tavily(handler) -> TavilyWebSearch:  # type: ignore[no-untyped-def]
    return TavilyWebSearch("tvly-test", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_tavily_sends_bearer_key_and_parses_results() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "results": [{"title": "T", "url": "https://a.example", "content": "C", "score": 0.5}, {"title": "x"}]
            },
        )

    results = _tavily(handler).search("journal issn", 3)

    assert seen["auth"] == "Bearer tvly-test"
    assert '"max_results":3' in str(seen["body"]).replace(" ", "")
    assert results == [WebResult("T", "https://a.example", "C", 0.5)]  # result without a URL dropped


def test_tavily_errors_become_web_search_errors() -> None:
    with pytest.raises(WebSearchError, match="HTTP 401"):
        _tavily(lambda r: httpx.Response(401, text="invalid api key")).search("q", 3)

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with pytest.raises(WebSearchError, match="ConnectError"):
        _tavily(offline).search("q", 3)


def test_web_search_is_off_without_a_key() -> None:
    assert providers.build_web_search(Settings(_env_file=None)) is None
    assert providers.build_web_search(Settings(_env_file=None, tavily_api_key="tvly-x")) is not None


def test_results_are_tagged_and_truncated_as_untrusted_data() -> None:
    long = WebResult('Title "with" <tags>', "https://x.example", "y" * 5000)
    text = format_web_results([long])
    assert text.startswith('<web_result index="1" url="https://x.example" title="Title \'with\' (tags)">')
    assert len(text) < 1400


def test_tool_returns_urls_as_artifact_and_reports_failures() -> None:
    tool = build_web_search_tool(FakeWebSearch([RESULT]), max_results=5)
    message = tool.invoke({"type": "tool_call", "name": "search_web", "args": {"query": "issn"}, "id": "w1"})
    assert "ISSN 0970-2555" in message.content
    assert message.artifact == ["https://journal.example/issn"]

    broken = build_web_search_tool(FakeWebSearch(error="HTTP 432: out of credits"), max_results=5)
    message = broken.invoke({"type": "tool_call", "name": "search_web", "args": {"query": "issn"}, "id": "w2"})
    assert "unavailable" in message.content and message.artifact == []


def test_agent_endpoint_returns_web_sources(harness: AppHarness) -> None:
    harness.web_search = FakeWebSearch([RESULT])
    call = AIMessage("", tool_calls=[{"name": "search_web", "args": {"query": "IIE journal ISSN"}, "id": "w1"}])
    with harness.client(call, "ISSN 0970-2555 (source: https://journal.example/issn).") as c:
        r = c.post("/api/v1/agent", json={"task": "What is the journal's ISSN?"})

    body = r.json()
    assert body["web_sources"] == ["https://journal.example/issn"]
    assert body["tool_calls"] == 1
    assert harness.web_search.queries == ["IIE journal ISSN"]


def test_agent_offers_web_tool_only_when_configured(harness: AppHarness) -> None:
    with harness.client("Answer.") as c:
        c.post("/api/v1/agent", json={"task": "anything"})
    assert "search_web" not in harness.llm.seen[0][0].content  # system prompt has no web section

    harness.web_search = FakeWebSearch([RESULT])
    with harness.client("Answer.") as c:
        c.post("/api/v1/agent", json={"task": "anything"})
    assert "search_web" in harness.llm.seen[0][0].content
