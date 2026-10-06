import httpx
import openai
from langchain_core.messages import AIMessage

from app.rag.prompts import NO_DOCUMENTS_ANSWER
from tests.conftest import AppHarness

INGEST_BODY = {"documents": [{"text": "Paris is the capital of France.", "source": "geo.md"}]}


def test_liveness(harness: AppHarness) -> None:
    with harness.client() as c:
        assert c.get("/health/live").json() == {"status": "ok"}


def test_readiness_ok(harness: AppHarness) -> None:
    with harness.client() as c:
        r = c.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"database": True}}


def test_readiness_fails_when_database_down(harness: AppHarness) -> None:
    harness.db_ready = False
    with harness.client() as c:
        r = c.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"database": False}


def test_ingest_then_query(harness: AppHarness) -> None:
    with harness.client("Paris [1].") as c:
        assert c.post("/api/v1/ingest", json=INGEST_BODY).json() == {"documents": 1, "chunks": 1}
        r = c.post("/api/v1/query", json={"question": "Capital of France?"})

    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == "Paris [1]."
    assert body["model"] == "gpt-4.1-nano"
    assert body["sources"][0]["source"] == "geo.md"


def test_query_with_empty_store(harness: AppHarness) -> None:
    with harness.client() as c:
        r = c.post("/api/v1/query", json={"question": "Anything?"})
    assert r.json()["answer"] == NO_DOCUMENTS_ANSWER
    assert r.json()["sources"] == []


def test_agent_endpoint(harness: AppHarness) -> None:
    tool_call = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "France"}, "id": "c1"}])
    with harness.client(tool_call, "Paris (geo.md).") as c:
        c.post("/api/v1/ingest", json=INGEST_BODY)
        r = c.post("/api/v1/agent", json={"task": "Capital of France?"})
    assert r.json() == {"answer": "Paris (geo.md).", "tool_calls": 1, "model": "gpt-4.1-nano"}


def test_agent_stops_at_iteration_limit(harness: AppHarness) -> None:
    looping = [
        AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "x"}, "id": f"c{i}"}])
        for i in range(10)
    ]
    with harness.client(*looping) as c:
        r = c.post("/api/v1/agent", json={"task": "loop forever"})
    assert r.status_code == 200
    assert "search limit" in r.json()["answer"]


def test_validation_rejects_empty_question(harness: AppHarness) -> None:
    with harness.client() as c:
        assert c.post("/api/v1/query", json={"question": ""}).status_code == 422


def test_llm_rate_limit_maps_to_429(harness: AppHarness, monkeypatch) -> None:
    request = httpx.Request("POST", "https://llm.test/chat/completions")
    error = openai.RateLimitError("quota", response=httpx.Response(429, request=request), body=None)

    with harness.client() as c:
        c.post("/api/v1/ingest", json=INGEST_BODY)

        def boom(*args, **kwargs):
            raise error

        monkeypatch.setattr(type(harness.llm), "invoke", boom)
        r = c.post("/api/v1/query", json={"question": "Capital?"})
    assert r.status_code == 429


def test_metrics_exposed(harness: AppHarness) -> None:
    with harness.client() as c:
        c.get("/health/live")
        c.post("/api/v1/query", json={"question": "Anything?"})
        text = c.get("/metrics/").text
    assert 'http_requests_total{method="GET",route="/health/live",status="200"}' in text
    assert 'http_requests_total{method="POST",route="/api/v1/query",status="200"}' in text
    assert "rag_chunks_ingested_total" in text
