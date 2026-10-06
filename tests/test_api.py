import json

import httpx
import openai
from langchain_core.messages import AIMessage

from app.rag.prompts import NO_DOCUMENTS_ANSWER
from tests.builders import make_pdf, make_xlsx
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
        ingested = c.post("/api/v1/ingest", json=INGEST_BODY).json()
        r = c.post("/api/v1/query", json={"question": "Capital of France?"})

    assert ingested == {
        "documents": 1,
        "chunks": 1,
        "chunking": "recursive",
        "results": [
            {
                "source": "geo.md",
                "status": "added",
                "chunking": "recursive",
                "chunks": 1,
                "added": 1,
                "removed": 0,
                "golden_questions": 0,
                "error": None,
            }
        ],
    }
    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == "Paris [1]."
    assert body["model"] == "gpt-4.1-nano"
    assert body["sources"][0]["source"] == "geo.md"


def test_ingest_accepts_a_chunking_strategy(harness: AppHarness) -> None:
    with harness.client() as c:
        r = c.post("/api/v1/ingest", json={**INGEST_BODY, "chunking": "parent_child"})
    assert r.status_code == 200
    assert r.json()["chunking"] == "parent_child"


def test_ingest_accepts_an_overlap_override_within_range(harness: AppHarness) -> None:
    with harness.client() as c:
        assert c.post("/api/v1/ingest", json={**INGEST_BODY, "chunk_overlap_pct": 20}).status_code == 200
        assert c.post("/api/v1/ingest", json={**INGEST_BODY, "chunk_overlap_pct": 80}).status_code == 422


def test_ingest_rejects_unknown_chunking_strategy(harness: AppHarness) -> None:
    with harness.client() as c:
        r = c.post("/api/v1/ingest", json={**INGEST_BODY, "chunking": "magic"})
    assert r.status_code == 422


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
    assert r.json() == {"answer": "Paris (geo.md).", "tool_calls": 1, "model": "gpt-4.1-nano", "web_sources": []}


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


def _provider_error(status_code: int, message: str) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://llm.test/embeddings")
    response = httpx.Response(status_code, request=request)
    return openai.PermissionDeniedError(message, response=response, body=None)


def test_euri_spent_daily_allowance_403_maps_to_429(harness: AppHarness, monkeypatch) -> None:
    error = _provider_error(403, "Your daily token allowance is used up. Add funds to your wallet")
    with harness.client() as c:
        c.post("/api/v1/ingest", json=INGEST_BODY)
        monkeypatch.setattr(type(harness.llm), "invoke", lambda *a, **k: (_ for _ in ()).throw(error))
        r = c.post("/api/v1/query", json={"question": "Capital?"})
    assert r.status_code == 429
    assert r.json()["detail"] == "LLM rate limit or daily quota reached, retry later"


def test_other_403_from_provider_stays_502(harness: AppHarness, monkeypatch) -> None:
    error = _provider_error(403, "Model access denied for this key")
    with harness.client() as c:
        c.post("/api/v1/ingest", json=INGEST_BODY)
        monkeypatch.setattr(type(harness.llm), "invoke", lambda *a, **k: (_ for _ in ()).throw(error))
        r = c.post("/api/v1/query", json={"question": "Capital?"})
    assert r.status_code == 502


def test_metrics_exposed(harness: AppHarness) -> None:
    with harness.client() as c:
        c.get("/health/live")
        c.post("/api/v1/query", json={"question": "Anything?"})
        text = c.get("/metrics/").text
    assert 'http_requests_total{method="GET",route="/health/live",status="200"}' in text
    assert 'http_requests_total{method="POST",route="/api/v1/query",status="200"}' in text
    assert "rag_chunks_ingested_total" in text


def test_metrics_moved_off_app_port_when_metrics_port_set(harness: AppHarness, monkeypatch) -> None:
    started: list[int] = []

    class FakeServer:
        def shutdown(self) -> None:
            started.append(-1)

    monkeypatch.setattr("app.main.start_http_server", lambda port: (started.append(port) or FakeServer(), None))
    harness.settings = harness.settings.model_copy(update={"metrics_port": 9090})
    with harness.client() as c:
        assert c.get("/metrics/").status_code == 404  # not exposed on the public app port
    assert started == [9090, -1]  # started on startup, shut down on exit


def _upload(c, files: list[tuple[str, bytes]], **form: str):  # type: ignore[no-untyped-def]
    return c.post("/api/v1/ingest/files", files=[("files", (name, data)) for name, data in files], data=form)


def test_file_upload_parses_each_type_and_reports_bad_files(harness: AppHarness) -> None:
    xlsx = make_xlsx({"Prices": [["Item", "Price"], ["Tea", 3]]})
    pdf = make_pdf(["Tea is grown in Assam."])
    with harness.client() as c:
        r = _upload(c, [("prices.xlsx", xlsx), ("tea.pdf", pdf), ("old.xls", b"x")])

    assert r.status_code == 200
    results = {d["source"]: d for d in r.json()["results"]}
    assert results["prices.xlsx"]["status"] == "added"
    assert results["prices.xlsx"]["chunking"] == "table"  # spreadsheets default to table chunking
    assert results["tea.pdf"]["chunking"] == "recursive"
    assert results["old.xls"]["status"] == "failed"
    assert "save it as .xlsx" in results["old.xls"]["error"]


def test_reuploading_the_same_file_is_skipped_and_a_changed_one_updated(harness: AppHarness) -> None:
    with harness.client() as c:
        first = _upload(c, [("notes.txt", b"Version one of the notes.")]).json()["results"][0]
        again = _upload(c, [("notes.txt", b"Version one of the notes.")]).json()["results"][0]
        changed = _upload(c, [("notes.txt", b"Version two of the notes.")]).json()["results"][0]

    assert first["status"] == "added"
    assert again["status"] == "unchanged" and again["added"] == 0
    assert changed["status"] == "updated" and changed["added"] == 1 and changed["removed"] == 1


def test_upload_rejects_files_over_the_size_limit(harness: AppHarness) -> None:
    harness.settings.max_upload_mb = 1
    with harness.client() as c:
        r = _upload(c, [("big.txt", b"x" * (1024 * 1024 + 1))])
    assert r.status_code == 413


def test_upload_overlap_out_of_range_is_rejected(harness: AppHarness) -> None:
    with harness.client() as c:
        assert _upload(c, [("a.txt", b"hello there")], chunk_overlap_pct="90").status_code == 422


def test_ingest_generates_golden_questions(harness: AppHarness) -> None:
    harness.settings.golden_questions_per_document = 2
    pair = {"question": "What is the capital of France?", "answer": "Paris", "evidence": "capital of France"}
    generated = json.dumps([{**pair, "passage": 1}])
    with harness.client(generated) as c:
        result = c.post("/api/v1/ingest", json=INGEST_BODY).json()["results"][0]
        golden = c.get("/api/v1/golden").json()

    assert result["golden_questions"] == 1
    assert golden["count"] == 1
    assert golden["items"][0] | {"id": "-"} == {
        "id": "-",
        "source": "geo.md",
        "question": "What is the capital of France?",
        "answer": "Paris",
        "evidence": "capital of France",
        "location": None,
        "origin": "generated",
    }


def test_failed_golden_generation_does_not_fail_the_upload(harness: AppHarness) -> None:
    harness.settings.golden_questions_per_document = 2
    with harness.client("this is not json") as c:
        r = c.post("/api/v1/ingest", json=INGEST_BODY)
    assert r.status_code == 200
    assert r.json()["results"][0]["golden_questions"] == 0
    assert r.json()["results"][0]["status"] == "added"


def test_import_golden_then_evaluate(harness: AppHarness) -> None:
    item = {
        "source": "geo.md",
        "question": "What is the capital of France?",
        "answer": "Paris",
        "evidence": "capital of France",
    }
    with harness.client("Paris [1].", '{"correct": true, "reason": "same"}') as c:
        c.post("/api/v1/ingest", json=INGEST_BODY)
        assert c.post("/api/v1/golden", json={"items": [item]}).json()["count"] == 1
        report = c.post("/api/v1/eval", json={"top_k": 2}).json()

    assert report["count"] == 1
    assert report["evidence_hit_rate"] == 1.0
    assert report["mrr"] == 1.0
    assert report["answer_accuracy"] == 1.0
    assert report["citation_accuracy"] == 1.0
    assert report["items"][0]["retrieved"] == ["geo.md"]


def test_evaluation_routes_are_admin_only(harness: AppHarness) -> None:
    with harness.client(role="user") as c:
        assert c.get("/api/v1/golden").status_code == 403
        assert c.post("/api/v1/eval", json={}).status_code == 403
        assert _upload(c, [("a.txt", b"hello")]).status_code == 403


def test_list_and_delete_documents_removes_chunks_and_golden(harness: AppHarness) -> None:
    item = {"source": "geo.md", "question": "What is the capital of France?", "answer": "Paris", "evidence": "capital"}
    with harness.client() as c:
        c.post("/api/v1/ingest", json=INGEST_BODY)
        c.post("/api/v1/golden", json={"items": [item]})
        listed = c.get("/api/v1/documents").json()
        deleted = c.delete("/api/v1/documents", params={"source": "geo.md"}).json()
        after = c.get("/api/v1/documents").json()
        golden_after = c.get("/api/v1/golden").json()
        missing = c.delete("/api/v1/documents", params={"source": "geo.md"})

    assert listed == {"count": 1, "documents": [{"source": "geo.md", "chunking": "recursive", "chunks": 1}]}
    assert deleted == {"source": "geo.md", "chunks_deleted": 1, "golden_deleted": 1}
    assert after["count"] == 0 and golden_after["count"] == 0
    assert harness.vector_store.store == {}
    assert missing.status_code == 404


def test_document_routes_are_admin_only(harness: AppHarness) -> None:
    with harness.client(role="user") as c:
        assert c.get("/api/v1/documents").status_code == 403
        assert c.delete("/api/v1/documents", params={"source": "x"}).status_code == 403
