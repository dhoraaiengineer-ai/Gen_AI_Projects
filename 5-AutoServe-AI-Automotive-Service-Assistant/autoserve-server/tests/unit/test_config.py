from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import ChainEntry, Settings, parse_chain
from app.core.db import engine_kwargs


def test_parse_chain_keeps_order_and_model_slashes() -> None:
    chain = parse_chain("euri:gpt-4.1-mini, groq:openai/gpt-oss-120b")
    assert chain == (ChainEntry("euri", "gpt-4.1-mini"), ChainEntry("groq", "openai/gpt-oss-120b"))


@pytest.mark.parametrize("raw", ["", "euri", "euri:", "openai:gpt-4o", " , "])
def test_parse_chain_rejects_bad_entries(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_chain(raw)


def test_agent_chain_must_not_include_gemini() -> None:
    with pytest.raises(ValidationError, match="gemini"):
        Settings(llm_agent_chain="euri:a,gemini:b")


def test_answer_chain_may_include_gemini() -> None:
    assert Settings(llm_answer_chain="euri:a,gemini:b").answer_chain[1].provider == "gemini"


@pytest.mark.parametrize("temp", [0.1, 0.6])
def test_temperature_outside_range_rejected(temp: float) -> None:
    with pytest.raises(ValidationError):
        Settings(llm_temperature=temp)


@pytest.mark.parametrize("temp", [0.2, 0.5])
def test_temperature_bounds_accepted(temp: float) -> None:
    assert Settings(llm_temperature=temp).llm_temperature == temp


def test_embedding_dimensions_must_be_1536() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_dimensions=1024)


def test_web_search_cannot_be_enabled() -> None:
    with pytest.raises(ValidationError, match="corpus"):
        Settings(web_search_enabled=True)


def test_max_retries_capped_at_two() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_max_retries=3)


def test_transaction_pooler_disables_statement_cache() -> None:
    assert engine_kwargs("transaction", 5)["connect_args"]["statement_cache_size"] == 0
    assert "statement_cache_size" not in engine_kwargs("session", 5)["connect_args"]
