"""Chat models from ``provider:model`` specs, with resilience and fallback chains.

Every provider is reached through its OpenAI-compatible API (``ChatOpenAI`` + ``base_url``), so
EURI, Gemini, Groq and OpenAI are interchangeable by configuration. Anthropic and Bedrock use their
own LangChain classes (optional dependencies) behind the same resilience wrapper.

``make_resilient(cls)`` subclasses a LangChain chat model and overrides ``_generate``,
``_agenerate``, ``_stream`` and ``_astream`` to add, per ``provider:model``:

* a circuit breaker (quota exhaustion opens it immediately so the chain falls back),
* error mapping to the taxonomy (quota/rate → 429, provider error → 502, unreachable → 503),
* one retry for transient failures (never for quota),
* latency, token and estimated-cost metrics.

Because only the private generation methods are overridden, ``bind_tools`` and
``with_structured_output`` keep working: they wrap the same model instance.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from typing import Any, Literal, cast

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from src.config.settings import ModelSpec, Settings
from src.core.circuit_breaker import BreakerRegistry, CircuitState
from src.core.errors import AppError, ProviderError, ProviderUnavailable, map_provider_exception
from src.core.metrics import (
    CIRCUIT_STATE,
    LLM_COST,
    LLM_FALLBACKS,
    LLM_LATENCY,
    LLM_REQUESTS,
    LLM_TOKENS,
)
from src.core.retry import retry_async, retry_sync
from src.core.tokens import current_meter

logger = logging.getLogger(__name__)

# Estimated list prices, USD per 1M tokens (input, output). Unknown models cost 0 in metrics.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-3.8-flash": (0.30, 2.50),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.10, 0.50),
    "qwen/qwen3-32b": (0.29, 0.59),
}


def _on_circuit_change(key: str, state: CircuitState) -> None:
    CIRCUIT_STATE.labels(key=key).set(int(state))


BREAKERS = BreakerRegistry(on_state_change=_on_circuit_change)


def _usage_from_message(message: BaseMessage) -> tuple[int, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)


def _usage_from_result(result: ChatResult) -> tuple[int, int]:
    if result.generations:
        tin, tout = _usage_from_message(result.generations[0].message)
        if tin or tout:
            return tin, tout
    usage = (result.llm_output or {}).get("token_usage") or {}
    return int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = PRICING_PER_MTOK.get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def _check_budget() -> None:
    """Refuse the call when this request's token budget is used up (ADR-029)."""
    meter = current_meter()
    if meter is not None:
        meter.ensure_available()


def _record_success(key: str, model: str, started: float, tokens_in: int, tokens_out: int) -> None:
    elapsed = time.perf_counter() - started
    meter = current_meter()
    if meter is not None:
        meter.record(key, tokens_in, tokens_out, estimate_cost(model, tokens_in, tokens_out))
    LLM_REQUESTS.labels(model=key, status="ok").inc()
    LLM_LATENCY.labels(model=key).observe(elapsed)
    LLM_TOKENS.labels(model=key, direction="in").inc(tokens_in)
    LLM_TOKENS.labels(model=key, direction="out").inc(tokens_out)
    LLM_COST.labels(model=key).inc(estimate_cost(model, tokens_in, tokens_out))
    logger.info(
        "llm call",
        extra={
            "model": key,
            "latency_ms": round(elapsed * 1000),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        },
    )


def _record_failure(key: str, started: float, error: AppError) -> None:
    LLM_REQUESTS.labels(model=key, status=error.code).inc()
    LLM_LATENCY.labels(model=key).observe(time.perf_counter() - started)
    logger.warning(
        "llm call failed", extra={"model": key, "error": error.code, "status": error.status_code}
    )


def make_resilient[M: BaseChatModel](base: type[M]) -> type[M]:
    """Return a subclass of ``base`` with breaker, error mapping, retry and metrics."""

    class Resilient(base):  # type: ignore[valid-type,misc]
        resilience_key: str = ""
        provider_name: str = "openai"
        chat_attempts: int = 2  # one retry for transient errors
        has_fallback: bool = False

        def _key(self) -> str:
            return self.resilience_key or f"{self.provider_name}:{getattr(self, 'model_name', '')}"

        def _model(self) -> str:
            return str(getattr(self, "model_name", "") or getattr(self, "model", ""))

        def _fail(self, exc: BaseException, started: float) -> AppError:
            error = map_provider_exception(exc, provider=self.provider_name)
            BREAKERS.get(self._key()).record_failure(error)
            _record_failure(self._key(), started, error)
            return error

        def _note_fallback(self) -> None:
            if self.has_fallback:
                LLM_FALLBACKS.labels(from_model=self._key()).inc()

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            breaker = BREAKERS.get(self._key())

            def once() -> ChatResult:
                _check_budget()
                breaker.before_call()
                started = time.perf_counter()
                try:
                    result: ChatResult = super(Resilient, self)._generate(
                        messages, stop=stop, run_manager=run_manager, **kwargs
                    )
                except Exception as exc:
                    raise self._fail(exc, started) from exc
                breaker.record_success()
                _record_success(self._key(), self._model(), started, *_usage_from_result(result))
                return result

            try:
                return retry_sync(once, attempts=self.chat_attempts, label=self._key())
            except AppError:
                self._note_fallback()
                raise

        async def _agenerate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            breaker = BREAKERS.get(self._key())

            async def once() -> ChatResult:
                _check_budget()
                breaker.before_call()
                started = time.perf_counter()
                try:
                    result: ChatResult = await super(Resilient, self)._agenerate(
                        messages, stop=stop, run_manager=run_manager, **kwargs
                    )
                except Exception as exc:
                    raise self._fail(exc, started) from exc
                breaker.record_success()
                _record_success(self._key(), self._model(), started, *_usage_from_result(result))
                return result

            try:
                return await retry_async(once, attempts=self.chat_attempts, label=self._key())
            except AppError:
                self._note_fallback()
                raise

        def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
            _check_budget()
            breaker = BREAKERS.get(self._key())
            breaker.before_call()
            started = time.perf_counter()
            tokens_in = tokens_out = 0
            try:
                for chunk in super()._stream(*args, **kwargs):
                    tin, tout = _usage_from_message(chunk.message)
                    tokens_in, tokens_out = tokens_in + tin, tokens_out + tout
                    yield chunk
            except Exception as exc:
                self._note_fallback()
                raise self._fail(exc, started) from exc
            breaker.record_success()
            _record_success(self._key(), self._model(), started, tokens_in, tokens_out)

        async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
            _check_budget()
            breaker = BREAKERS.get(self._key())
            breaker.before_call()
            started = time.perf_counter()
            tokens_in = tokens_out = 0
            try:
                async for chunk in super()._astream(*args, **kwargs):
                    tin, tout = _usage_from_message(chunk.message)
                    tokens_in, tokens_out = tokens_in + tin, tokens_out + tout
                    yield chunk
            except Exception as exc:
                self._note_fallback()
                raise self._fail(exc, started) from exc
            breaker.record_success()
            _record_success(self._key(), self._model(), started, tokens_in, tokens_out)

    Resilient.__name__ = Resilient.__qualname__ = f"Resilient{base.__name__}"
    return Resilient


ResilientChatOpenAI = make_resilient(ChatOpenAI)

OPENAI_COMPATIBLE = frozenset({"euri", "gemini", "groq", "openai"})
ChainName = Literal["answer", "agent"]


def _needs_low_reasoning(model: str) -> bool:
    m = model.lower()
    return "gpt-oss" in m or m.startswith(("gemini-3", "o3", "o4"))


class LlmFactory:
    """Builds resilient chat models and fallback chains from settings."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[tuple[str, bool, float | None, int | None], BaseChatModel] = {}

    # ------------------------------------------------------------------ endpoints
    def _endpoint(self, provider: str) -> tuple[str | None, SecretStr | None]:
        s = self.settings
        return {
            "euri": (s.euri_base_url, s.euri_api_key),
            "gemini": (s.gemini_base_url, s.gemini_api_key),
            "groq": (s.groq_base_url, s.groq_api_key),
            "openai": (None, s.openai_api_key),
            "anthropic": (None, s.anthropic_api_key),
            "bedrock": (None, s.aws_access_key_id),
        }.get(provider, (None, None))

    def is_configured(self, spec: ModelSpec) -> bool:
        return self._endpoint(spec.provider)[1] is not None

    def configured(self, chain: Sequence[ModelSpec]) -> list[ModelSpec]:
        specs = [s for s in chain if self.is_configured(s)]
        skipped = [s.key for s in chain if s not in specs]
        if skipped:
            logger.warning("models without API keys skipped", extra={"models": skipped})
        if not specs:
            raise ProviderUnavailable(
                "no configured model in chain", details={"chain": [s.key for s in chain]}
            )
        return specs

    # ------------------------------------------------------------------ single models
    def chat(
        self,
        spec: ModelSpec,
        *,
        has_fallback: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        cache_key = (spec.key, has_fallback, temperature, max_tokens)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._build(spec, has_fallback, temperature, max_tokens)
        return self._cache[cache_key]

    def _build(
        self, spec: ModelSpec, has_fallback: bool, temperature: float | None, max_tokens: int | None
    ) -> BaseChatModel:
        base_url, api_key = self._endpoint(spec.provider)
        if api_key is None:
            raise ProviderUnavailable(f"{spec.provider} has no API key configured")
        temp = self.settings.llm_temperature if temperature is None else temperature
        common: dict[str, Any] = {
            "resilience_key": spec.key,
            "provider_name": spec.provider,
            "has_fallback": has_fallback,
        }
        if spec.provider in OPENAI_COMPATIBLE:
            kwargs: dict[str, Any] = {
                "model": spec.model,
                "api_key": api_key,
                "temperature": temp,
                "timeout": self.settings.llm_timeout_seconds,
                "max_retries": 0,
                "stream_usage": True,
                "use_responses_api": False,
            }
            if base_url:
                kwargs["base_url"] = base_url
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            if _needs_low_reasoning(spec.model):
                kwargs["reasoning_effort"] = "low"
            if spec.provider == "groq" and "qwen" in spec.model.lower():
                kwargs["extra_body"] = {"reasoning_format": "hidden"}
            return ResilientChatOpenAI(**kwargs, **common)
        return self._build_optional(spec, temp, max_tokens, common)

    def _build_optional(
        self, spec: ModelSpec, temp: float, max_tokens: int | None, common: dict[str, Any]
    ) -> BaseChatModel:
        if spec.provider == "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic  # noqa: PLC0415 - optional
            except ImportError as exc:
                raise ProviderError("install langchain-anthropic to use anthropic models") from exc
            cls = make_resilient(ChatAnthropic)
            return cast(
                BaseChatModel,
                cls(
                    model=spec.model,
                    api_key=self.settings.anthropic_api_key,
                    temperature=temp,
                    max_tokens=max_tokens or 1024,
                    max_retries=0,
                    **common,
                ),
            )
        if spec.provider == "bedrock":
            try:
                from langchain_aws import ChatBedrockConverse  # noqa: PLC0415 - optional
            except ImportError as exc:
                raise ProviderError("install langchain-aws to use bedrock models") from exc
            cls = make_resilient(ChatBedrockConverse)
            return cast(
                BaseChatModel,
                cls(
                    model=spec.model,
                    region_name=self.settings.aws_region,
                    temperature=temp,
                    max_tokens=max_tokens,
                    **common,
                ),
            )
        raise ProviderError(f"unsupported provider {spec.provider!r}")

    # ------------------------------------------------------------------ chains
    def _chain(self, name: ChainName) -> list[ModelSpec]:
        chain = self.settings.answer_chain if name == "answer" else self.settings.agent_chain
        return self.configured(chain)

    def _with_fallbacks(
        self,
        name: ChainName,
        build: Callable[[BaseChatModel], Runnable[Any, Any]],
        max_tokens: int | None = None,
    ) -> Runnable[Any, Any]:
        specs = self._chain(name)
        runnables = [
            build(self.chat(s, has_fallback=i < len(specs) - 1, max_tokens=max_tokens))
            for i, s in enumerate(specs)
        ]
        if len(runnables) == 1:
            return runnables[0]
        return runnables[0].with_fallbacks(runnables[1:], exceptions_to_handle=(AppError,))

    def answer_model(
        self, max_tokens: int | None = None
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        """Narrative/answer chain (EURI → Gemini → Groq by default)."""
        return self._with_fallbacks("answer", lambda m: m, max_tokens)

    def agent_model(
        self, tools: Sequence[Any], *, tool_choice: str | None = None, max_tokens: int | None = None
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Tool-calling chain: tools bound to every model, then fallbacks."""
        return self._with_fallbacks(
            "agent", lambda m: m.bind_tools(tools, tool_choice=tool_choice), max_tokens
        )

    def structured_model[S: BaseModel](
        self, schema: type[S], *, chain: ChainName = "answer", max_tokens: int | None = None
    ) -> Runnable[LanguageModelInput, S]:
        """Structured output (pydantic) with fallbacks."""
        return self._with_fallbacks(
            chain, lambda m: m.with_structured_output(schema, method="function_calling"), max_tokens
        )
