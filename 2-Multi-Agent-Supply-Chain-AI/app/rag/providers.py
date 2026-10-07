"""Provider adapters — the ONLY module (with app/container.py) that imports provider SDKs.

Every model is called through its OpenAI-compatible API, so providers are interchangeable by config.
"""

from __future__ import annotations

import base64
import io
import logging
import time
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from typing import Any

import httpx
import openai
import redis.asyncio as aioredis
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import PrivateAttr
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import BreakerRegistry, CircuitBreaker
from app.core.config import ModelSpec, Settings
from app.core.errors import (
    CircuitOpen,
    ProviderBadRequest,
    ProviderFailure,
    ProviderQuotaExceeded,
    ProviderRateLimited,
    ProviderUnavailable,
)
from app.core.kv import InMemoryKV
from app.core.llm import with_fallbacks  # noqa: F401 - re-exported for callers of this module
from app.core.metrics import CACHE, LLM_COST, LLM_LATENCY, LLM_TOKENS, WEB_SEARCHES
from app.core.ports import OcrResult, WebResult, WebSearchResponse

logger = logging.getLogger(__name__)

# USD per 1M tokens (input, output). Used for cost tracking only — estimates for non-published prices.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gemini-3.5-flash": (0.30, 2.50),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "qwen/qwen3.8-27b": (0.29, 0.59),
}
QUOTA_HINTS = ("quota", "insufficient", "credit", "balance", "exceeded your", "limit reached", "wallet")


# ----------------------------------------------------------------------------- error mapping
def map_provider_error(exc: BaseException) -> ProviderFailure:
    """Normalise SDK/HTTP errors. Some gateways report an exhausted quota as 403 — detect it from the message."""
    if isinstance(exc, ProviderFailure):
        return exc
    message = str(exc)[:300]
    lowered = message.lower()
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError, httpx.TimeoutException, httpx.ConnectError)):
        return ProviderUnavailable(f"provider unreachable: {type(exc).__name__}")
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status in (402, 403) and any(h in lowered for h in QUOTA_HINTS):
        return ProviderQuotaExceeded(message)
    if status == 429:
        return ProviderQuotaExceeded(message) if any(h in lowered for h in QUOTA_HINTS) else ProviderRateLimited(message)
    if isinstance(status, int) and status >= 500:
        return ProviderFailure(f"provider error {status}")
    if isinstance(status, int) and 400 <= status < 500:
        return ProviderBadRequest(f"provider rejected request ({status}): {message}")
    return ProviderFailure(f"{type(exc).__name__}: {message}")


def _record_usage(model: str, result: ChatResult | None, seconds: float, outcome: str) -> None:
    LLM_LATENCY.labels(model, outcome).observe(seconds)
    if result is None or not result.generations:
        return
    usage = getattr(result.generations[0].message, "usage_metadata", None) or {}
    tin, tout = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    if tin or tout:
        LLM_TOKENS.labels(model, "input").inc(tin)
        LLM_TOKENS.labels(model, "output").inc(tout)
        pin, pout = MODEL_PRICES.get(model, (0.0, 0.0))
        LLM_COST.labels(model).inc((tin * pin + tout * pout) / 1_000_000)


# ----------------------------------------------------------------------------- chat model with circuit breaker
class ResilientChatOpenAI(ChatOpenAI):
    """ChatOpenAI whose generation paths go through a circuit breaker and normalised errors.

    Overriding `_generate`/`_agenerate`/`_stream`/`_astream` (not `invoke`) keeps `bind_tools`,
    `with_structured_output` and the LangChain response cache working.
    """

    spec_label: str = ""
    _breaker: CircuitBreaker | None = PrivateAttr(default=None)

    def attach_breaker(self, breaker: CircuitBreaker) -> ResilientChatOpenAI:
        self._breaker = breaker
        return self

    def _guard(self) -> None:
        if self._breaker is not None and not self._breaker.allow():
            raise CircuitOpen(f"circuit open for {self.spec_label}")

    def _ok(self) -> None:
        if self._breaker is not None:
            self._breaker.record_success()

    def _fail(self, err: ProviderFailure) -> None:
        if self._breaker is not None:
            self._breaker.record_failure(err.is_outage)
        logger.warning("llm call failed", extra={"model": self.spec_label, "error": err.code, "detail": err.message[:200]})

    def _generate(
        self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any
    ) -> ChatResult:
        self._guard()
        started = time.perf_counter()
        try:
            result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            err = map_provider_error(exc)
            self._fail(err)
            _record_usage(self.model_name, None, time.perf_counter() - started, err.code)
            raise err from exc
        self._ok()
        _record_usage(self.model_name, result, time.perf_counter() - started, "ok")
        return result

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._guard()
        started = time.perf_counter()
        try:
            result = await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            err = map_provider_error(exc)
            self._fail(err)
            _record_usage(self.model_name, None, time.perf_counter() - started, err.code)
            raise err from exc
        self._ok()
        _record_usage(self.model_name, result, time.perf_counter() - started, "ok")
        return result

    def _stream(
        self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any
    ) -> Iterator[ChatGenerationChunk]:
        self._guard()
        try:
            yield from super()._stream(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            err = map_provider_error(exc)
            self._fail(err)
            raise err from exc
        self._ok()

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        self._guard()
        started = time.perf_counter()
        try:
            async for chunk in super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                yield chunk
        except Exception as exc:
            err = map_provider_error(exc)
            self._fail(err)
            LLM_LATENCY.labels(self.model_name, err.code).observe(time.perf_counter() - started)
            raise err from exc
        self._ok()
        LLM_LATENCY.labels(self.model_name, "ok").observe(time.perf_counter() - started)


class LlmFactory:
    """Builds chat models and fallback chains from `provider:model` specs."""

    def __init__(self, settings: Settings, breakers: BreakerRegistry) -> None:
        self._settings = settings
        self._breakers = breakers

    def available(self, spec: ModelSpec) -> bool:
        _, key = self._settings.provider_credentials(spec.provider)
        return bool(key.get_secret_value())

    def chat(
        self, spec: ModelSpec, *, temperature: float | None = None, streaming: bool = False, max_tokens: int | None = None
    ) -> ResilientChatOpenAI:
        base_url, key = self._settings.provider_credentials(spec.provider)
        extra: dict[str, Any] = {}
        model = spec.model.lower()
        # Reasoning models spend max_tokens on thinking: keep effort low.
        if "gpt-oss" in model or model.startswith("gemini-3"):
            extra["reasoning_effort"] = "low"
        extra_body: dict[str, Any] = {}
        if spec.provider == "groq" and "qwen" in model:
            extra_body["reasoning_format"] = "hidden"
        llm = ResilientChatOpenAI(
            model=spec.model,
            base_url=base_url,
            api_key=key,
            temperature=self._settings.llm_temperature if temperature is None else temperature,
            max_tokens=max_tokens or self._settings.llm_max_tokens,
            timeout=self._settings.llm_timeout_seconds,
            max_retries=1,  # the fallback chain is the better retry
            streaming=streaming,
            stream_usage=True,
            spec_label=str(spec),
            extra_body=extra_body or None,
            **extra,
        )
        return llm.attach_breaker(self._breakers.get(str(spec)))

    def models(self, specs: Sequence[ModelSpec], **kwargs: Any) -> list[ResilientChatOpenAI]:
        built = [self.chat(s, **kwargs) for s in specs if self.available(s)]
        if not built:
            raise ProviderUnavailable("no LLM provider has an API key configured")
        return built


# ----------------------------------------------------------------------------- embeddings
def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, ProviderFailure) and exc.retryable and exc.is_outage


class ResilientEmbeddings:
    """Embeddings can't fall back to another model (vectors aren't comparable), so they retry with backoff."""

    def __init__(self, settings: Settings) -> None:
        spec = settings.embedding_spec
        base_url, key = settings.provider_credentials(spec.provider)
        self.model = spec.model
        self.dimensions = settings.embedding_dimensions
        self._client = OpenAIEmbeddings(
            model=spec.model,
            base_url=base_url,
            api_key=key,
            dimensions=settings.embedding_dimensions,
            check_embedding_ctx_length=False,  # non-OpenAI providers expect raw strings, not token ids
            chunk_size=64,
            max_retries=0,
            request_timeout=settings.llm_timeout_seconds,
        )

    async def _call(self, fn: Callable[[], Any]) -> Any:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=1, max=12),
            retry=retry_if_exception(_retryable),
            reraise=True,
        ):
            with attempt:
                try:
                    return await fn()
                except ProviderFailure:
                    raise
                except Exception as exc:
                    raise map_provider_error(exc) from exc
        raise ProviderFailure("embedding retries exhausted")  # pragma: no cover - reraise=True

    def _check(self, vectors: list[list[float]]) -> list[list[float]]:
        for v in vectors:
            if len(v) != self.dimensions:
                raise ProviderBadRequest(f"embedding has {len(v)} dimensions, expected {self.dimensions}")
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._check(await self._call(lambda: self._client.aembed_documents(texts)))

    async def embed_query(self, text: str) -> list[float]:
        return self._check([await self._call(lambda: self._client.aembed_query(text))])[0]


# ----------------------------------------------------------------------------- web search (Tavily)
class TavilySearch:
    URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        self._key = api_key
        self._timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> WebSearchResponse:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self.URL, json={"api_key": self._key, "query": query, "max_results": max_results, "search_depth": "basic"}
                )
                resp.raise_for_status()
        except Exception as exc:
            WEB_SEARCHES.labels("error").inc()
            raise map_provider_error(exc) from exc
        WEB_SEARCHES.labels("ok").inc()
        data = resp.json()
        return WebSearchResponse(
            query=query,
            results=[
                WebResult(r.get("title", ""), r.get("url", ""), r.get("content", "")[:1500], float(r.get("score", 0)))
                for r in data.get("results", [])
            ],
        )


# ----------------------------------------------------------------------------- OCR
class TesseractOcr:
    name = "tesseract"

    def __init__(self, languages: str = "eng") -> None:
        import pytesseract  # imported lazily: the binary only exists in the container image

        self._tess = pytesseract
        self._lang = languages

    def image_to_text(self, image_bytes: bytes) -> OcrResult:
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        data = self._tess.image_to_data(image, lang=self._lang, output_type=self._tess.Output.DICT)
        words = [w for w, c in zip(data["text"], data["conf"], strict=True) if w.strip() and float(c) >= 0]
        confs = [float(c) for w, c in zip(data["text"], data["conf"], strict=True) if w.strip() and float(c) >= 0]
        text = self._tess.image_to_string(image, lang=self._lang)
        return (
            OcrResult(text=text, confidence=sum(confs) / len(confs) if confs else 0.0, engine=self.name)
            if words
            else OcrResult("", 0.0, self.name)
        )


class VisionLlmOcr:
    """OCR with a multimodal LLM for difficult scans (handwriting, low contrast)."""

    name = "vision_llm"

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    def image_to_text(self, image_bytes: bytes) -> OcrResult:
        b64 = base64.b64encode(image_bytes).decode()
        msg = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": "Transcribe all text in this document image exactly. Preserve tables as Markdown. Output only the text.",
                },
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]
        )
        text = str(self._model.invoke([msg]).content)
        return OcrResult(text=text, confidence=85.0 if text.strip() else 0.0, engine=self.name)


# ----------------------------------------------------------------------------- key-value store
class ResilientRedisKV:
    """Redis-backed store that degrades to an in-process store on any Redis error (never fails a request)."""

    def __init__(self, url: str) -> None:
        self._redis = aioredis.from_url(url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5)
        self._fallback = InMemoryKV()
        self._down_until = 0.0

    async def _run(self, op: str, fn: Callable[[], Any], fallback: Callable[[], Any]) -> Any:
        if time.monotonic() < self._down_until:
            return await fallback()
        try:
            return await fn()
        except Exception as exc:  # any Redis failure → degrade for 30 s
            self._down_until = time.monotonic() + 30
            CACHE.labels("redis", "error").inc()
            logger.warning("redis unavailable, using in-process store", extra={"op": op, "error": type(exc).__name__})
            return await fallback()

    async def get(self, key: str) -> str | None:
        return await self._run("get", lambda: self._redis.get(key), lambda: self._fallback.get(key))

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        await self._run("set", lambda: self._redis.set(key, value, ex=ttl_seconds), lambda: self._fallback.set(key, value, ttl_seconds))

    async def delete(self, key: str) -> None:
        await self._run("delete", lambda: self._redis.delete(key), lambda: self._fallback.delete(key))

    async def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        async def do() -> int:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                if ttl_seconds:
                    pipe.expire(key, ttl_seconds, nx=True)
                res = await pipe.execute()
            return int(res[0])

        return int(await self._run("incr", do, lambda: self._fallback.incr(key, ttl_seconds)))

    async def lpush_trim(self, key: str, value: str, max_len: int, ttl_seconds: int | None = None) -> None:
        async def do() -> None:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.lpush(key, value)
                pipe.ltrim(key, 0, max_len - 1)
                if ttl_seconds:
                    pipe.expire(key, ttl_seconds)
                await pipe.execute()

        await self._run("lpush", do, lambda: self._fallback.lpush_trim(key, value, max_len, ttl_seconds))

    async def lrange(self, key: str, count: int) -> list[str]:
        return list(await self._run("lrange", lambda: self._redis.lrange(key, 0, count - 1), lambda: self._fallback.lrange(key, count)))

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()
