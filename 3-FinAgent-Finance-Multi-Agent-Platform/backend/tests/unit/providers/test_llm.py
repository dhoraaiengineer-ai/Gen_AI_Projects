"""ResilientChatOpenAI against a fake OpenAI-compatible server (httpx2 MockTransport).

Exercises the real ChatOpenAI + openai SDK code paths offline: error mapping from real SDK
exceptions, retry, circuit breaker, metrics, bind_tools, structured output, streaming, async and
fallback chains.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx2
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from prometheus_client import REGISTRY
from pydantic import BaseModel

from src.config.settings import ModelSpec, Settings
from src.core.circuit_breaker import CircuitState
from src.core.errors import CircuitOpen, ProviderError, ProviderUnavailable, QuotaExceeded
from src.core.tokens import BudgetExceeded, start_meter, stop_meter
from src.providers.llm import BREAKERS, LlmFactory, ResilientChatOpenAI

Handler = Callable[[httpx2.Request], httpx2.Response]


def completion(
    content: str | None = "Hello", tool_calls: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4.1-mini",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


def tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "call_1",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class FakeServer:
    """Scripted responses; records request bodies."""

    def __init__(self, *responses: httpx2.Response) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content or b"{}"))
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


def ok(body: dict[str, Any]) -> httpx2.Response:
    return httpx2.Response(200, json=body)


def err(status: int, message: str) -> httpx2.Response:
    return httpx2.Response(status, json={"error": {"message": message, "type": "x", "code": None}})


def model(server: FakeServer, key: str = "euri:gpt-4.1-mini", **kwargs: Any) -> ResilientChatOpenAI:
    provider, _, name = key.partition(":")
    return ResilientChatOpenAI(
        model=name,
        api_key="test-key",
        base_url="http://fake/v1",
        max_retries=0,
        use_responses_api=False,
        stream_usage=True,
        temperature=0.2,
        http_client=httpx2.Client(transport=httpx2.MockTransport(server)),
        http_async_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server)),
        resilience_key=key,
        provider_name=provider,
        **kwargs,
    )


def metric(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture(autouse=True)
def fresh_breakers() -> Iterator[None]:
    BREAKERS.reset()
    yield
    BREAKERS.reset()


def test_success_returns_message_and_records_usage() -> None:
    before = metric("finagent_llm_tokens_total", model="euri:gpt-4.1-mini", direction="in")
    reply = model(FakeServer(ok(completion("Hi there")))).invoke([HumanMessage("hello")])
    assert reply.content == "Hi there"
    after = metric("finagent_llm_tokens_total", model="euri:gpt-4.1-mini", direction="in")
    assert after - before == 11


def test_quota_429_is_not_retried_and_opens_circuit() -> None:
    server = FakeServer(err(429, "You exceeded your current quota"))
    m = model(server)
    with pytest.raises(QuotaExceeded) as info:
        m.invoke([HumanMessage("hi")])
    assert info.value.status_code == 429
    assert len(server.requests) == 1
    assert BREAKERS.get("euri:gpt-4.1-mini").state is CircuitState.OPEN
    with pytest.raises(CircuitOpen):  # skipped without a request
        m.invoke([HumanMessage("again")])
    assert len(server.requests) == 1


def test_gateway_403_quota_maps_to_429() -> None:
    server = FakeServer(err(403, "Daily token quota exhausted for this model"))
    with pytest.raises(QuotaExceeded):
        model(server).invoke([HumanMessage("hi")])


def test_transient_503_is_retried_once() -> None:
    server = FakeServer(err(503, "overloaded"), ok(completion("recovered")))
    assert model(server).invoke([HumanMessage("hi")]).content == "recovered"
    assert len(server.requests) == 2


def test_persistent_500_maps_to_provider_error_and_trips_breaker() -> None:
    server = FakeServer(*[err(500, "boom")] * 3)
    m = model(server)
    for _ in range(3):  # not retried: one request per call; breaker threshold is 3
        with pytest.raises(ProviderError) as info:
            m.invoke([HumanMessage("hi")])
        assert info.value.status_code == 502
    assert len(server.requests) == 3
    assert BREAKERS.get("euri:gpt-4.1-mini").state is CircuitState.OPEN


def test_bind_tools_still_works() -> None:
    server = FakeServer(ok(completion(None, [tool_call("get_stock_price", {"ticker": "NVTK"})])))

    def get_stock_price(ticker: str) -> str:
        """Latest closing price for a ticker."""
        return "1"

    reply = model(server).bind_tools([get_stock_price]).invoke([HumanMessage("price of NVTK?")])
    assert isinstance(reply, AIMessage)
    assert reply.tool_calls[0]["name"] == "get_stock_price"
    assert reply.tool_calls[0]["args"] == {"ticker": "NVTK"}
    assert server.requests[0]["tools"][0]["function"]["name"] == "get_stock_price"


class Intent(BaseModel):
    intent: str
    tickers: list[str]


def test_structured_output_still_works() -> None:
    server = FakeServer(
        ok(
            completion(
                None, [tool_call("Intent", {"intent": "portfolio_risk", "tickers": ["NVTK"]})]
            )
        )
    )
    result = model(server).with_structured_output(Intent, method="function_calling").invoke("x")
    assert result == Intent(intent="portfolio_risk", tickers=["NVTK"])


async def test_async_invoke() -> None:
    reply = await model(FakeServer(ok(completion("async ok")))).ainvoke([HumanMessage("hi")])
    assert reply.content == "async ok"


def test_streaming_yields_tokens() -> None:
    def chunk(text: str) -> dict[str, Any]:
        delta = {"role": "assistant", "content": text}
        return {
            "id": "c",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }

    chunks = [chunk("Hel"), chunk("lo")]
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    server = FakeServer(
        httpx2.Response(200, text=body, headers={"content-type": "text/event-stream"})
    )
    tokens = [str(c.content) for c in model(server).stream([HumanMessage("hi")])]
    assert "".join(tokens) == "Hello"


def test_fallback_chain_moves_to_next_model_and_counts_it() -> None:
    primary = model(FakeServer(err(429, "quota exceeded")), has_fallback=True)
    backup = model(FakeServer(ok(completion("from groq"))), key="groq:openai/gpt-oss-120b")
    before = metric("finagent_llm_fallbacks_total", from_model="euri:gpt-4.1-mini")
    chain = primary.with_fallbacks([backup], exceptions_to_handle=(QuotaExceeded,))
    assert chain.invoke([HumanMessage("hi")]).content == "from groq"
    assert metric("finagent_llm_fallbacks_total", from_model="euri:gpt-4.1-mini") - before == 1


# ---------------------------------------------------------------- factory


def settings(**kwargs: Any) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_factory_skips_models_without_keys() -> None:
    factory = LlmFactory(settings(euri_api_key="k", groq_api_key=None, gemini_api_key=None))
    assert [s.key for s in factory.configured(factory.settings.answer_chain)] == [
        "euri:gpt-4.1-mini"
    ]


def test_factory_without_any_key_raises_unavailable() -> None:
    with pytest.raises(ProviderUnavailable):
        LlmFactory(settings()).answer_model()


def test_factory_builds_provider_specific_options() -> None:
    factory = LlmFactory(settings(groq_api_key="k", euri_api_key="k"))
    groq = factory.chat(factory.settings.agent_chain[1])
    assert isinstance(groq, ResilientChatOpenAI)
    assert groq.openai_api_base == "https://api.groq.com/openai/v1"
    assert groq.max_retries == 0
    qwen = factory.chat(ModelSpec.parse("groq:qwen/qwen3-32b"))
    assert isinstance(qwen, ResilientChatOpenAI)
    assert qwen.extra_body == {"reasoning_format": "hidden"}
    oss = factory.chat(ModelSpec.parse("groq:openai/gpt-oss-20b"))
    assert isinstance(oss, ResilientChatOpenAI)
    assert oss.reasoning_effort == "low"


def test_default_agent_chain_excludes_gemini() -> None:
    assert all(s.provider != "gemini" for s in settings().agent_chain)


# ---------------------------------------------------------------- token budgets (ADR-029)


def test_request_budget_blocks_further_calls_and_records_usage() -> None:
    server = FakeServer(ok(completion("first")))
    meter, token = start_meter(15)  # one call uses 18 tokens (11 in + 7 out)
    try:
        m = model(server)
        assert m.invoke([HumanMessage("hi")]).content == "first"
        assert meter.total == 18 and meter.calls == 1
        with pytest.raises(BudgetExceeded):
            m.invoke([HumanMessage("again")])
    finally:
        stop_meter(token)
    assert len(server.requests) == 1  # the refused call never reached the provider


def test_max_tokens_is_sent_to_the_provider() -> None:
    server = FakeServer(ok(completion("short")))
    factory = LlmFactory(settings(euri_api_key="k"))
    chat = factory.chat(ModelSpec.parse("euri:gpt-4.1-mini"), max_tokens=60)
    assert isinstance(chat, ResilientChatOpenAI)
    patched = model(server, max_tokens=60)
    patched.invoke([HumanMessage("hi")])
    body = server.requests[0]
    assert body.get("max_tokens") == 60 or body.get("max_completion_tokens") == 60
