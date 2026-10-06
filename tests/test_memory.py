"""Conversation memory, answer caching and the audit log through the API."""

import logging

import pytest

from app.rag.cache import InMemoryKeyValueStore
from app.rag.memory import ChatTurn, ConversationMemory, InMemoryConversationStore
from tests.conftest import AppHarness, make_token

INGEST = {"documents": [{"text": "The journal ISSN is 2799-0417. It is published monthly.", "source": "j.md"}]}


def test_short_term_window_and_reload_from_long_term() -> None:
    long_term = InMemoryConversationStore()
    short_term = InMemoryKeyValueStore()
    memory = ConversationMemory(long_term, short_term, window=4, ttl_seconds=60)
    for i in range(3):
        memory.remember("u1", "s1", f"q{i}", f"a{i}")

    assert [t.content for t in memory.recent("u1", "s1")] == ["q1", "a1", "q2", "a2"]  # last 4 messages
    assert len(memory.history("u1", "s1")) == 6  # long-term keeps everything

    short_term.delete_prefix("memory:")  # Redis restarted / TTL expired
    assert [t.content for t in memory.recent("u1", "s1")] == ["q1", "a1", "q2", "a2"]  # reloaded from Postgres


def test_sessions_are_isolated_per_user() -> None:
    memory = ConversationMemory(InMemoryConversationStore(), InMemoryKeyValueStore(), 4, 60)
    memory.remember("alice", "s1", "secret question", "answer")
    assert memory.recent("bob", "s1") == []
    assert [s.title for s in memory.sessions("alice")] == ["secret question"]
    assert memory.sessions("bob") == []


def test_follow_up_is_rewritten_with_the_conversation(harness: AppHarness) -> None:
    with harness.client("The ISSN is 2799-0417 [1].", "Is it published monthly?", "Yes, monthly [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        c.post("/api/v1/query", json={"question": "What is the journal's ISSN?", "session_id": "s1"})
        follow_up = c.post("/api/v1/query", json={"question": "how often is it out?", "session_id": "s1"}).json()
        conversation = c.get("/api/v1/conversations/s1").json()
        sessions = c.get("/api/v1/conversations").json()

    assert follow_up["standalone_question"] == "Is it published monthly?"
    assert follow_up["answer"] == "Yes, monthly [1]."
    rewrite_prompt = harness.llm.seen[1][1].content
    assert "What is the journal's ISSN?" in rewrite_prompt and "how often is it out?" in rewrite_prompt
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant", "user", "assistant"]
    assert sessions["sessions"][0]["title"] == "What is the journal's ISSN?"


def test_without_session_there_is_no_rewrite_or_memory(harness: AppHarness) -> None:
    with harness.client("Answer [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        r = c.post("/api/v1/query", json={"question": "What is the ISSN?"}).json()
    assert r["standalone_question"] is None
    assert len(harness.llm.seen) == 1


def test_other_users_cannot_read_a_conversation(harness: AppHarness) -> None:
    with harness.client("Answer [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        c.post("/api/v1/query", json={"question": "What is the ISSN?", "session_id": "mine"})
        other = {"Authorization": f"Bearer {make_token(sub='someone-else')}"}
        assert c.get("/api/v1/conversations/mine", headers=other).json()["messages"] == []


def test_invalid_session_id_is_rejected(harness: AppHarness) -> None:
    with harness.client() as c:
        r = c.post("/api/v1/query", json={"question": "q", "session_id": "../etc/passwd"})
    assert r.status_code == 422


def test_repeated_question_is_served_from_cache_until_documents_change(harness: AppHarness) -> None:
    with harness.client("First [1].", "After update [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        first = c.post("/api/v1/query", json={"question": "What is the ISSN?"}).json()
        repeat = c.post("/api/v1/query", json={"question": "  what is the issn "}).json()
        c.post("/api/v1/ingest", json={"documents": [{"text": "Updated: ISSN 1111-2222.", "source": "j.md"}]})
        after = c.post("/api/v1/query", json={"question": "What is the ISSN?"}).json()

    assert (first["cached"], repeat["cached"], after["cached"]) == (False, True, False)
    assert repeat["answer"] == "First [1]."
    assert after["answer"] == "After update [1]."


def test_cache_can_be_disabled(harness: AppHarness) -> None:
    harness.settings.cache_enabled = False
    with harness.client("One [1].", "Two [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        c.post("/api/v1/query", json={"question": "What is the ISSN?"})
        second = c.post("/api/v1/query", json={"question": "What is the ISSN?"}).json()
    assert second["cached"] is False and second["answer"] == "Two [1]."


@pytest.fixture
def audit_records(caplog: pytest.LogCaptureFixture):  # type: ignore[no-untyped-def]
    """create_app() resets the root handlers, so capture straight from the audit logger."""
    audit = logging.getLogger("app.audit")
    audit.addHandler(caplog.handler)
    audit.setLevel(logging.INFO)
    yield caplog
    audit.removeHandler(caplog.handler)


def test_every_action_is_audit_logged(harness: AppHarness, audit_records: pytest.LogCaptureFixture) -> None:
    caplog = audit_records
    with harness.client("Answer [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        c.post("/api/v1/query", json={"question": "What is the ISSN?", "session_id": "s9"})

    records = [r for r in caplog.records if r.name == "app.audit"]
    events = [r.getMessage() for r in records]
    assert events.count("api request") == 2
    assert "documents ingested" in events and "question answered" in events
    answered = next(r for r in records if r.getMessage() == "question answered")
    assert (answered.user_id, answered.session_id, answered.question) == ("user-123", "s9", "What is the ISSN?")
    request_line = next(r for r in records if r.getMessage() == "api request" and r.route == "/api/v1/query")
    assert request_line.status == 200 and request_line.user_email == "dev@example.com"


def test_audit_content_can_be_turned_off(harness: AppHarness, audit_records: pytest.LogCaptureFixture) -> None:
    caplog = audit_records
    harness.settings.audit_log_content = False
    with harness.client("Answer [1].") as c:
        c.post("/api/v1/ingest", json=INGEST)
        c.post("/api/v1/query", json={"question": "What is the ISSN?"})
    answered = next(r for r in caplog.records if r.getMessage() == "question answered")
    assert not hasattr(answered, "question") and not hasattr(answered, "answer")
    assert answered.model == "gpt-4.1-nano"


def test_chat_turn_roles() -> None:
    assert ChatTurn("user", "hi").role == "user"
