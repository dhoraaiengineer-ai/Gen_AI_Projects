import pytest

from app.config import Settings
from app.rag.providers import connect_args_for


def test_supabase_url_gets_psycopg_driver() -> None:
    s = Settings(_env_file=None, database_url="postgresql://u:p@db.example.supabase.co:5432/postgres")
    assert s.sqlalchemy_database_url == "postgresql+psycopg://u:p@db.example.supabase.co:5432/postgres"


def test_explicit_driver_url_is_untouched() -> None:
    url = "postgresql+psycopg://u:p@localhost:5432/rag"
    assert Settings(_env_file=None, database_url=url).sqlalchemy_database_url == url


def test_missing_database_url_raises() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _ = Settings(_env_file=None).sqlalchemy_database_url


def test_secrets_are_masked_in_repr() -> None:
    s = Settings(_env_file=None, euri_api_key="euri-supersecret", database_url="postgresql://u:hunter2@h/db")
    text = repr(s)
    assert "supersecret" not in text
    assert "hunter2" not in text


def test_transaction_pooler_disables_prepared_statements() -> None:
    url = "postgresql+psycopg://postgres.ref:pw@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
    assert connect_args_for(url) == {"prepare_threshold": None}


def test_other_ports_keep_prepared_statements() -> None:
    assert connect_args_for("postgresql+psycopg://rag:rag@localhost:5432/rag") == {}
