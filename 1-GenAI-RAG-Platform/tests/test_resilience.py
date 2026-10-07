"""Circuit breaker, caches, Redis store degradation and the provider-level breaker wiring."""

import httpx
import openai
import pytest
import redis
from langchain_core.messages import AIMessage, HumanMessage

from app.config import Settings
from app.core.circuit import BreakerRegistry, CircuitBreaker, CircuitOpenError, State
from app.rag import providers
from app.rag.cache import AnswerCache, InMemoryKeyValueStore, PromptCache, normalize_question
from tests.conftest import fake_llm


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _status_error(code: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://llm.test")
    return openai.APIStatusError("boom", response=httpx.Response(code, request=request), body=None)


# ---------- circuit breaker ----------


def test_breaker_opens_after_threshold_and_rejects_fast() -> None:
    clock = Clock()
    breaker = CircuitBreaker("groq:x", failure_threshold=2, reset_seconds=30, clock=clock)
    breaker.record_failure()
    assert breaker.state == State.CLOSED
    breaker.record_failure()
    assert breaker.state == State.OPEN
    with pytest.raises(CircuitOpenError) as exc:
        breaker.before_call()
    assert exc.value.retry_in == 30


def test_breaker_half_open_allows_one_trial_then_closes_or_reopens() -> None:
    clock = Clock()
    breaker = CircuitBreaker("b", failure_threshold=1, reset_seconds=10, clock=clock)
    breaker.record_failure()
    clock.now += 10
    assert breaker.state == State.HALF_OPEN

    breaker.before_call()  # the trial call
    with pytest.raises(CircuitOpenError):
        breaker.before_call()  # a second concurrent call is still rejected
    breaker.record_failure()
    assert breaker.state == State.OPEN  # failed trial reopens immediately

    clock.now += 10
    breaker.before_call()
    breaker.record_success()
    assert breaker.state == State.CLOSED
    breaker.before_call()  # closed again: calls go through


def test_success_resets_the_failure_count() -> None:
    breaker = CircuitBreaker("b", failure_threshold=2, clock=Clock())
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.state == State.CLOSED


def test_registry_shares_one_breaker_per_name() -> None:
    registry = BreakerRegistry(3, 60)
    assert registry.get("euri:gpt") is registry.get("euri:gpt")
    assert registry.get("euri:gpt") is not registry.get("groq:gpt")


def test_only_outages_trip_the_breaker() -> None:
    assert providers._counts_as_outage(_status_error(429))
    assert providers._counts_as_outage(_status_error(503))
    assert providers._counts_as_outage(_status_error(403))  # EURI's spent allowance
    assert not providers._counts_as_outage(_status_error(400))  # our bad request, not their outage
    assert not providers._counts_as_outage(ValueError("x"))


def test_open_circuit_skips_the_provider_without_a_network_call() -> None:
    settings = Settings(_env_file=None, euri_api_key="k")
    registry = BreakerRegistry(1, 60)
    llm = providers.build_chat_model(settings, "gpt-4.1-nano", breakers=registry)
    registry.get("euri:gpt-4.1-nano").record_failure()  # trip it

    with pytest.raises(CircuitOpenError):
        llm.invoke([HumanMessage("hi")])  # would need the network if the breaker let it through


def test_circuit_open_error_triggers_the_fallback_chain() -> None:
    assert CircuitOpenError in providers.FALLBACK_EXCEPTIONS


# ---------- caches ----------


def test_kv_store_ttl_and_eviction() -> None:
    clock = Clock()
    store = InMemoryKeyValueStore(max_entries=2, clock=clock)
    store.set("a", "1", ttl_seconds=10)
    clock.now += 10
    assert store.get("a") is None  # expired
    store.set("b", "2", 0)
    store.set("c", "3", 0)
    store.set("d", "4", 0)
    assert store.get("b") is None and store.get("d") == "4"  # oldest evicted
    assert store.incr("v") == 1 and store.incr("v") == 2


def test_answer_cache_normalizes_and_invalidates_on_document_changes() -> None:
    cache = AnswerCache(InMemoryKeyValueStore(), "docs", ttl_seconds=60)
    cache.set("What is the ISSN?", 4, {"answer": "2799-0417"})

    assert cache.get("  what is the   issn ", 4) == {"answer": "2799-0417"}
    assert cache.get("What is the ISSN?", 8) is None  # different top_k
    cache.invalidate()
    assert cache.get("What is the ISSN?", 4) is None


def test_normalize_question() -> None:
    assert normalize_question("  What is  the ISSN?? ") == "what is the issn"


def test_prompt_cache_serves_repeated_prompts_without_calling_the_model() -> None:
    llm = fake_llm("first answer")  # only one scripted response: a second real call would fail
    llm.cache = PromptCache(InMemoryKeyValueStore(), "docs", ttl_seconds=60)

    assert llm.invoke([HumanMessage("same prompt")]).content == "first answer"
    # Only one response is scripted: had the second call reached the model, it would raise StopIteration.
    assert llm.invoke([HumanMessage("same prompt")]).content == "first answer"


# ---------- Redis store ----------


class BrokenRedis:
    def __getattr__(self, name: str):  # every command fails like a dropped connection
        def fail(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise redis.ConnectionError("down")

        return fail


def test_redis_outage_degrades_to_cache_misses() -> None:
    store = providers.RedisKeyValueStore(BrokenRedis())  # type: ignore[arg-type]
    assert store.get("k") is None
    store.set("k", "v", 10)  # no exception
    assert store.incr("k") == 0
    assert store.ping() is False


def test_kv_store_is_in_memory_without_redis_url() -> None:
    assert isinstance(providers.build_kv_store(Settings(_env_file=None)), InMemoryKeyValueStore)
    store = providers.build_kv_store(Settings(_env_file=None, redis_url="redis://localhost:6399/0"))
    assert isinstance(store, providers.RedisKeyValueStore)  # lazy: no connection until first use


def test_fake_llm_helper_still_scripts_responses() -> None:
    assert fake_llm(AIMessage("x")).invoke("q").content == "x"
