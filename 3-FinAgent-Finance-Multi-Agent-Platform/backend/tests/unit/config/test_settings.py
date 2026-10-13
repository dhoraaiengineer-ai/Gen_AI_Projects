"""Settings: chain parsing, temperature bounds, URL building, shorthand, secrets."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config.settings import ModelSpec, Settings, parse_chain


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_defaults_are_valid_and_offline() -> None:
    s = make()
    assert s.demo_mode is True
    assert s.answer_chain[0].key == "euri:gpt-4.1-mini"
    assert all(m.provider != "gemini" for m in s.agent_chain)
    assert s.database_configured is False


def test_chain_parsing() -> None:
    chain = parse_chain(" euri:gpt-4.1-mini , groq:openai/gpt-oss-120b ")
    assert [c.key for c in chain] == ["euri:gpt-4.1-mini", "groq:openai/gpt-oss-120b"]
    assert ModelSpec.parse("GROQ:qwen/qwen3-32b").key == "groq:qwen/qwen3-32b"


@pytest.mark.parametrize("bad", ["", "gpt-4", "euri:", ":model", "acme:model", "euri:a,euri:a"])
def test_invalid_chains_are_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        make(llm_answer_chain=bad)


@pytest.mark.parametrize("temperature", [0.0, 0.19, 0.51, 1.0])
def test_temperature_must_be_between_0_2_and_0_5(temperature: float) -> None:
    with pytest.raises(ValidationError, match=r"between 0\.2 and 0\.5"):
        make(llm_temperature=temperature)


def test_temperature_bounds_are_inclusive() -> None:
    assert make(llm_temperature=0.2).llm_temperature == 0.2
    assert make(llm_temperature=0.5).llm_temperature == 0.5


def test_shorthand_overrides_both_chains() -> None:
    s = make(llm_provider="groq", llm_model="openai/gpt-oss-120b")
    assert [m.key for m in s.answer_chain] == ["groq:openai/gpt-oss-120b"]
    assert [m.key for m in s.agent_chain] == ["groq:openai/gpt-oss-120b"]


def test_shorthand_requires_both_values() -> None:
    with pytest.raises(ValidationError, match="both LLM_PROVIDER and LLM_MODEL"):
        make(llm_provider="groq")


def test_database_urls_encode_password_and_use_two_poolers() -> None:
    s = make(db_host="db.example", db_user="postgres.ref", db_password="p@ss:w/rd#1")
    assert (
        s.app_database_url
        == "postgresql+psycopg://postgres.ref:p%40ss%3Aw%2Frd%231@db.example:6543/postgres"
    )
    assert s.session_database_url.endswith("@db.example:5432/postgres")


def test_explicit_database_url_wins() -> None:
    s = make(database_url="postgresql+psycopg://u:p@h:5432/d", db_host="ignored")
    assert s.app_database_url == "postgresql+psycopg://u:p@h:5432/d"


def test_missing_database_config_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="database not configured"):
        _ = make().app_database_url


def test_blank_values_become_none_and_secrets_are_masked() -> None:
    s = make(euri_api_key="", groq_api_key="gsk_secret_value_123")
    assert s.euri_api_key is None
    assert "gsk_secret_value_123" not in repr(s)
    assert s.groq_api_key is not None
    assert s.groq_api_key.get_secret_value() == "gsk_secret_value_123"
