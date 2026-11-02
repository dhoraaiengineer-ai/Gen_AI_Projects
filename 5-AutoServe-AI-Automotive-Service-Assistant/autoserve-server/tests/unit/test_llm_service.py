"""LLMService chain fallback, timeouts, and usage recording (ADR-008) — no network."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.core.config import ChainEntry, Settings
from app.core.errors import LlmUnavailable
from app.services.llm_service import CallMeta, FakeLLM, LLMService, UsageRecord


class Out(BaseModel):
    ok: bool


class FakeClient:
    def __init__(self, behaviour: Any) -> None:
        self.behaviour = behaviour

    def with_structured_output(self, schema: type[BaseModel], include_raw: bool) -> FakeClient:
        return self

    async def ainvoke(self, messages: list[Any]) -> Any:
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


def _settings() -> Settings:
    return Settings(
        llm_agent_chain="euri:a1,groq:a2,groq:a3",
        llm_answer_chain="euri:b1,gemini:b2",
        llm_timeout_s=30,
        llm_fallback_timeout_s=10,
    )


def _service(behaviours: dict[str, Any]) -> tuple[LLMService, list[UsageRecord], list[tuple[str, float]]]:
    records: list[UsageRecord] = []
    created: list[tuple[str, float]] = []

    async def recorder(rec: UsageRecord) -> None:
        records.append(rec)

    def factory(entry: ChainEntry, timeout: float) -> Any:
        created.append((entry.model, timeout))
        return FakeClient(behaviours[entry.model])

    return LLMService(_settings(), recorder, factory), records, created  # type: ignore[arg-type]


RAW_OK = AIMessage(content="", usage_metadata={"input_tokens": 11, "output_tokens": 3, "total_tokens": 14})
META = CallMeta(purpose="test")
MSGS = [HumanMessage("hi")]


async def test_primary_success_records_one_ok_call() -> None:
    svc, records, created = _service({"a1": {"raw": RAW_OK, "parsed": Out(ok=True)}})
    assert (await svc.structured(Out, MSGS, META)).ok
    assert [(r.fallback_index, r.outcome, r.input_tokens) for r in records] == [(0, "ok", 11)]
    assert created == [("a1", 30)]


async def test_falls_back_with_shorter_timeout_and_records_each_attempt() -> None:
    svc, records, created = _service(
        {
            "a1": TimeoutError("primary down"),
            "a2": {"raw": RAW_OK, "parsed": None},  # invalid structured output
            "a3": {"raw": RAW_OK, "parsed": Out(ok=True)},
        }
    )
    assert (await svc.structured(Out, MSGS, META)).ok
    assert [(r.model, r.outcome) for r in records] == [("a1", "error"), ("a2", "invalid_output"), ("a3", "ok")]
    assert created == [("a1", 30), ("a2", 10), ("a3", 10)]


async def test_all_entries_failing_raises_llm_unavailable() -> None:
    svc, records, _ = _service({"a1": RuntimeError(), "a2": RuntimeError(), "a3": RuntimeError()})
    with pytest.raises(LlmUnavailable):
        await svc.structured(Out, MSGS, META)
    assert len(records) == 3


async def test_text_uses_answer_chain() -> None:
    svc, records, created = _service({"b1": RuntimeError(), "b2": AIMessage(content=" hello ")})
    assert await svc.text(MSGS, META) == "hello"
    assert [c[0] for c in created] == ["b1", "b2"] and records[-1].provider == "gemini"


async def test_recorder_failure_does_not_break_the_call() -> None:
    async def broken(_: UsageRecord) -> None:
        raise RuntimeError("db down")

    svc = LLMService(_settings(), broken, lambda e, t: FakeClient({"raw": RAW_OK, "parsed": Out(ok=True)}))  # type: ignore[arg-type,return-value]
    assert (await svc.structured(Out, MSGS, META)).ok


async def test_fake_llm_queues_and_records() -> None:
    fake = FakeLLM(structured=[{"ok": True}], texts=["t"])
    assert (await fake.structured(Out, MSGS, META)).ok
    assert await fake.text(MSGS, META) == "t"
    assert [c[0] for c in fake.calls] == ["structured", "text"]
    with pytest.raises(LlmUnavailable):
        await fake.text(MSGS, META)
