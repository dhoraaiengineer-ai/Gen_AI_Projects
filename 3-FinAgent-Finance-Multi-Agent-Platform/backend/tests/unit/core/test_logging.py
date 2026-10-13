"""Log formatters print extra= fields and request context; secrets in extras are masked."""

from __future__ import annotations

import json
import logging

from src.core.context import request_id_var
from src.core.logging import ContextFilter, JsonFormatter, TextFormatter


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    for k, v in extra.items():
        setattr(record, k, v)
    ContextFilter().filter(record)
    return record


def test_text_format_prints_extra_fields_and_request_id() -> None:
    token = request_id_var.set("req_abc12345")
    try:
        line = TextFormatter().format(_record(table="market_data", rows=10))
    finally:
        request_id_var.reset(token)
    assert "hello world" in line
    assert "request_id=req_abc12345" in line
    assert 'extra={"table": "market_data", "rows": 10}' in line


def test_json_format_is_valid_json_with_extras() -> None:
    payload = json.loads(JsonFormatter().format(_record(seconds=1.5)))
    assert payload["msg"] == "hello world"
    assert payload["seconds"] == 1.5
    assert payload["level"] == "INFO"


def test_secret_like_extra_keys_are_masked() -> None:
    line = TextFormatter().format(_record(api_key="sk-live", db_password="x", user_token="y"))
    assert "sk-live" not in line
    assert '"api_key": "***"' in line
    assert '"db_password": "***"' in line


def test_usage_fields_are_not_mistaken_for_secrets() -> None:
    line = TextFormatter().format(_record(tokens_in=120, tokens_out=40))
    assert '"tokens_in": 120' in line
