"""The ONLY place an LLM is called (CLAUDE.md §10, ADR-008).

Two ordered chains with fallback: AGENT (structured output / tools) and ANSWER (free text). The primary entry uses
LLM_TIMEOUT_S; fallbacks use the shorter LLM_FALLBACK_TIMEOUT_S. Each attempt is recorded in llm_usage.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

import structlog
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import ChainEntry, Settings, get_settings
from app.core.errors import LlmUnavailable

T = TypeVar("T", bound=BaseModel)
Chain = Literal["agent", "answer"]
log = structlog.get_logger("llm")


@dataclass(frozen=True)
class CallMeta:
    purpose: str
    node: str | None = None
    ro_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class UsageRecord:
    meta: CallMeta
    chain: str
    fallback_index: int
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    outcome: str  # ok | error | invalid_output


UsageRecorder = Callable[[UsageRecord], Awaitable[None]]


class LLM(Protocol):
    async def structured(self, schema: type[T], messages: Sequence[BaseMessage], meta: CallMeta) -> T: ...

    async def text(self, messages: Sequence[BaseMessage], meta: CallMeta) -> str: ...


def _usage(raw: Any) -> tuple[int | None, int | None]:
    um = getattr(raw, "usage_metadata", None) or {}
    return um.get("input_tokens"), um.get("output_tokens")


class LLMService:
    def __init__(
        self,
        settings: Settings | None = None,
        recorder: UsageRecorder | None = None,
        client_factory: Callable[[ChainEntry, float], ChatOpenAI] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.recorder = recorder
        self._factory = client_factory or self._client

    def _client(self, entry: ChainEntry, timeout: float) -> ChatOpenAI:
        base_url, key = self.settings.provider_credentials(entry.provider)
        if key is None:
            raise LlmUnavailable(f"No API key for provider {entry.provider}.")
        return ChatOpenAI(
            model=entry.model,
            base_url=base_url,
            api_key=key,
            temperature=self.settings.llm_temperature,
            timeout=timeout,
            max_retries=self.settings.llm_max_retries,
        )

    def _chain(self, chain: Chain) -> tuple[ChainEntry, ...]:
        return self.settings.agent_chain if chain == "agent" else self.settings.answer_chain

    async def _record(self, rec: UsageRecord) -> None:
        log.info(
            "llm_call",
            purpose=rec.meta.purpose,
            chain=rec.chain,
            fallback_index=rec.fallback_index,
            provider=rec.provider,
            model=rec.model,
            latency_ms=rec.latency_ms,
            outcome=rec.outcome,
            input_tokens=rec.input_tokens,
            output_tokens=rec.output_tokens,
        )
        if self.recorder is not None:
            try:
                await self.recorder(rec)
            except Exception:  # usage logging must never break the request
                log.exception("llm_usage_record_failed")

    async def _run(self, chain: Chain, meta: CallMeta, call: Callable[[ChatOpenAI], Awaitable[tuple[Any, Any]]]) -> Any:
        errors: list[str] = []
        for idx, entry in enumerate(self._chain(chain)):
            timeout = self.settings.llm_timeout_s if idx == 0 else self.settings.llm_fallback_timeout_s
            started = time.perf_counter()
            outcome, raw, result = "error", None, None
            try:
                raw, result = await call(self._factory(entry, timeout))
                outcome = "ok" if result is not None else "invalid_output"
            except LlmUnavailable:
                raise
            except Exception as exc:  # provider/network/parsing failure → try the next entry
                errors.append(f"{entry.provider}:{entry.model}: {type(exc).__name__}")
            tokens_in, tokens_out = _usage(raw)
            await self._record(
                UsageRecord(
                    meta=meta,
                    chain=chain,
                    fallback_index=idx,
                    provider=entry.provider,
                    model=entry.model,
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    outcome=outcome,
                )
            )
            if outcome == "ok":
                return result
            if outcome == "invalid_output":
                errors.append(f"{entry.provider}:{entry.model}: invalid structured output")
        log.error("llm_chain_exhausted", chain=chain, purpose=meta.purpose, errors=errors)
        raise LlmUnavailable()

    async def structured(self, schema: type[T], messages: Sequence[BaseMessage], meta: CallMeta) -> T:
        async def call(client: ChatOpenAI) -> tuple[Any, Any]:
            out = await client.with_structured_output(schema, include_raw=True).ainvoke(list(messages))
            parsed = out.get("parsed") if isinstance(out, dict) else None
            return (out.get("raw") if isinstance(out, dict) else None), (parsed if isinstance(parsed, schema) else None)

        return await self._run("agent", meta, call)  # type: ignore[no-any-return]

    async def text(self, messages: Sequence[BaseMessage], meta: CallMeta) -> str:
        async def call(client: ChatOpenAI) -> tuple[Any, Any]:
            msg = await client.ainvoke(list(messages))
            content = str(msg.content).strip()
            return msg, (content or None)

        return await self._run("answer", meta, call)  # type: ignore[no-any-return]


class FakeLLM:
    """Deterministic test double. Responses are queued per method; every call is recorded."""

    def __init__(self, structured: Sequence[Any] = (), texts: Sequence[str] = ()) -> None:
        self._structured = list(structured)
        self._texts = list(texts)
        self.calls: list[tuple[str, CallMeta, list[BaseMessage]]] = []

    async def structured(self, schema: type[T], messages: Sequence[BaseMessage], meta: CallMeta) -> T:
        self.calls.append(("structured", meta, list(messages)))
        if not self._structured:
            raise LlmUnavailable()
        item = self._structured.pop(0)
        if isinstance(item, Exception):
            raise item
        result = item(messages) if callable(item) else item
        return result if isinstance(result, schema) else schema.model_validate(result)

    async def text(self, messages: Sequence[BaseMessage], meta: CallMeta) -> str:
        self.calls.append(("text", meta, list(messages)))
        if not self._texts:
            raise LlmUnavailable()
        return self._texts.pop(0)


def db_usage_recorder() -> UsageRecorder:
    """Writes each attempt to llm_usage in its own short transaction."""
    from app.core.db import get_sessionmaker
    from app.models import LlmUsage

    async def record(rec: UsageRecord) -> None:
        async with get_sessionmaker()() as s, s.begin():
            s.add(
                LlmUsage(
                    request_id=rec.meta.request_id,
                    trace_id=rec.meta.trace_id,
                    ro_id=rec.meta.ro_id,
                    node=rec.meta.node,
                    purpose=rec.meta.purpose,
                    chain=rec.chain,
                    fallback_index=rec.fallback_index,
                    model=rec.model,
                    provider=rec.provider,
                    input_tokens=rec.input_tokens,
                    output_tokens=rec.output_tokens,
                    cost_usd=None,  # price table arrives with observability (P4-3); never guessed
                    latency_ms=rec.latency_ms,
                    outcome=rec.outcome,
                )
            )

    return record
