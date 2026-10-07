"""Web search as an external tool for the research agent. Provider-neutral: Tavily lives in providers.py.

Web pages are untrusted input, so results are wrapped in tagged blocks the agent prompt tells the model
to treat as data, and long snippets are truncated.
"""

from dataclasses import dataclass
from typing import Protocol

MAX_SNIPPET_CHARS = 800  # keeps an agent step inside free-tier token-per-minute limits


class WebSearchError(RuntimeError):
    """The search provider failed (network, auth, quota). The agent gets a message, not a crash."""


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    content: str
    score: float = 0.0


class WebSearch(Protocol):
    def search(self, query: str, max_results: int) -> list[WebResult]: ...


def _attr(value: str) -> str:
    return value.replace('"', "'").replace("<", "(").replace(">", ")")


def format_web_results(results: list[WebResult]) -> str:
    return "\n\n".join(
        f'<web_result index="{i}" url="{_attr(r.url)}" title="{_attr(r.title)}">\n'
        f"{r.content[:MAX_SNIPPET_CHARS]}\n</web_result>"
        for i, r in enumerate(results, start=1)
    )
