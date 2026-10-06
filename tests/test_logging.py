import logging

from app.core.logging import TextFormatter


def _record(msg: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, msg, None, None)
    record.__dict__.update(extra)
    return record


def test_text_format_appends_extra_fields() -> None:
    line = TextFormatter().format(_record("llm error", upstream_status=400, upstream_message="model not found"))
    assert line.endswith("app.test llm error | upstream_status=400 upstream_message='model not found'")


def test_text_format_without_extras_is_unchanged() -> None:
    assert TextFormatter().format(_record("startup complete")).endswith("app.test startup complete")
