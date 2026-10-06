"""Provider selection only: clients are constructed but no request is sent."""

import pytest
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import Settings, parse_model_chain
from app.rag import providers

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, euri_api_key="euri-test", gemini_api_key="gemini-test", **overrides)


def test_chat_defaults_to_euri() -> None:
    llm = providers.build_chat_model(_settings())
    assert isinstance(llm, ChatOpenAI)
    assert str(llm.openai_api_base).startswith("https://api.euron.one")
    assert llm.reasoning_effort is None


def test_gemini_fallback_goes_direct_to_google_with_low_reasoning() -> None:
    llm = providers.build_fallback_model(_settings(), "gemini-3.5-flash", "gemini")
    assert isinstance(llm, ChatOpenAI)
    assert llm.openai_api_base == GEMINI_URL
    assert llm.openai_api_key.get_secret_value() == "gemini-test"
    assert llm.reasoning_effort == "low"


def test_empty_fallback_model_disables_fallback() -> None:
    assert providers.build_fallback_model(_settings(), "", "gemini") is None


def test_gemini_embeddings_request_the_configured_dimensions() -> None:
    emb = providers.build_embeddings(_settings(embedding_provider="gemini", embedding_model="gemini-embedding-001"))
    assert isinstance(emb, OpenAIEmbeddings)
    assert emb.openai_api_base == GEMINI_URL
    assert emb.dimensions == 1536


def test_euri_embeddings_leave_dimensions_to_the_model() -> None:
    assert providers.build_embeddings(_settings()).dimensions is None


def test_gemini_provider_without_key_fails_fast() -> None:
    settings = Settings(_env_file=None, euri_api_key="euri-test", embedding_provider="gemini")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        providers.build_embeddings(settings)


def test_gemini_key_is_masked_in_repr() -> None:
    assert "gemini-test" not in repr(_settings())


GROQ_URL = "https://api.groq.com/openai/v1"


def test_parse_model_chain() -> None:
    assert parse_model_chain(" groq:openai/gpt-oss-120b , gemini:gemini-3.5-flash ,") == [
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-3.5-flash"),
    ]
    assert parse_model_chain("") == []
    for bad in ("openai/gpt-oss-120b", "mistral:large", "groq:"):
        with pytest.raises(ValueError):
            parse_model_chain(bad)


def test_malformed_fallback_setting_fails_at_startup() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, agent_extra_fallbacks="gpt-oss-120b")


def test_fallback_chain_keeps_order_and_routes_each_provider() -> None:
    settings = _settings(groq_api_key="groq-test")
    chain = providers.build_fallback_chain(settings, ("gemini", "gemini-3.5-flash"), "groq:openai/gpt-oss-120b")

    assert [(m.model_name, m.openai_api_base) for m in chain] == [
        ("gemini-3.5-flash", GEMINI_URL),
        ("openai/gpt-oss-120b", GROQ_URL),
    ]
    assert chain[1].openai_api_key.get_secret_value() == "groq-test"
    assert chain[1].reasoning_effort == "low"  # gpt-oss is a reasoning model


def test_empty_first_fallback_is_skipped() -> None:
    chain = providers.build_fallback_chain(_settings(groq_api_key="g"), ("euri", ""), "groq:qwen/qwen3.8-27b")
    assert [m.model_name for m in chain] == ["qwen/qwen3.8-27b"]
    assert chain[0].reasoning_effort is None


def test_groq_without_key_fails_fast() -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        providers.build_fallback_chain(_settings(), None, "groq:openai/gpt-oss-120b")
