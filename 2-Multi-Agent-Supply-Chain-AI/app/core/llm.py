"""Model-agnostic LLM helpers (LangChain core only — no provider SDKs)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.errors import ProviderFailure


def with_fallbacks(
    models: Sequence[BaseChatModel], transform: Callable[[BaseChatModel], Runnable[Any, Any]] | None = None
) -> Runnable[Any, Any]:
    """Apply `transform` (e.g. bind_tools / with_structured_output) to each model, then chain fallbacks.

    Only provider failures trigger the next model; programming errors surface immediately.
    """
    runnables = [transform(m) if transform else m for m in models]
    if len(runnables) == 1:
        return runnables[0]
    return runnables[0].with_fallbacks(runnables[1:], exceptions_to_handle=(ProviderFailure,))
