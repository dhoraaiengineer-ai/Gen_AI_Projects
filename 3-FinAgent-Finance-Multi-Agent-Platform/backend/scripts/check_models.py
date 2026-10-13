"""Verify every configured model live.

* answer chain: one short call per model
* agent chain: a real tool-call round trip per model (tool call → tool result → final answer)
* embeddings: one call, dimension check

Each model is called directly (no fallbacks) so a broken model is visible. Prints the planned call
count before running. Usage: uv run python -m scripts.check_models [--yes]
"""

from __future__ import annotations

import argparse
import sys
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from src.config.settings import ModelSpec, get_settings
from src.core.errors import AppError
from src.core.logging import configure_logging
from src.providers.embeddings import build_embeddings
from src.providers.llm import LlmFactory

TOOL_PRICE = "182.40"


@tool
def get_stock_price(ticker: str) -> str:
    """Return the latest closing price for a ticker symbol."""
    return TOOL_PRICE


def _check_answer(factory: LlmFactory, spec: ModelSpec) -> str:
    model = factory.chat(spec, max_tokens=20)
    reply = model.invoke([HumanMessage("Reply with exactly the word: READY")])
    text = str(reply.content).strip()
    if "READY" not in text.upper():
        raise RuntimeError(f"unexpected reply {text[:60]!r}")
    return f"replied {text[:20]!r}"


def _check_agent(factory: LlmFactory, spec: ModelSpec) -> str:
    model = factory.chat(spec, max_tokens=200).bind_tools([get_stock_price])
    question = HumanMessage("What is the latest closing price of NVTK? Use the tool.")
    first = model.invoke([question])
    if not isinstance(first, AIMessage) or not first.tool_calls:
        raise RuntimeError("model did not call the tool")
    call = first.tool_calls[0]
    if call["name"] != "get_stock_price" or str(call["args"].get("ticker", "")).upper() != "NVTK":
        raise RuntimeError(f"wrong tool call {call['name']}({call['args']})")
    final = model.invoke([question, first, ToolMessage(TOOL_PRICE, tool_call_id=call["id"] or "")])
    if TOOL_PRICE not in str(final.content):
        raise RuntimeError(f"final answer lacks the tool value: {str(final.content)[:80]!r}")
    return "tool round trip ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()
    configure_logging("WARNING")
    settings = get_settings()
    factory = LlmFactory(settings)
    answer = [s for s in settings.answer_chain if factory.is_configured(s)]
    agent = [s for s in settings.agent_chain if factory.is_configured(s)]
    calls = len(answer) + 2 * len(agent) + 1
    print(
        f"Planned live calls: {calls} ({len(answer)} answer, {2 * len(agent)} agent round trip, "
        f"1 embedding), roughly {calls * 350} tokens in total."
    )
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return 1

    failures = 0
    checks = [("answer", s, _check_answer) for s in answer] + [
        ("agent", s, _check_agent) for s in agent
    ]
    for kind, spec, fn in checks:
        started = time.perf_counter()
        try:
            detail = fn(factory, spec)
            status = "OK  "
        except (AppError, RuntimeError) as exc:
            failures += 1
            status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
            if isinstance(exc, AppError) and exc.details:
                detail += f" {exc.details}"
        print(f"{status} {kind:6} {spec.key:45} {time.perf_counter() - started:5.1f}s  {detail}")

    started = time.perf_counter()
    try:
        vector = build_embeddings(settings).embed_query("FinAgent embedding check")
        print(
            f"OK   embed  {settings.embedding_provider}:{settings.embedding_model:34} "
            f"{time.perf_counter() - started:5.1f}s  dimensions={len(vector)}"
        )
    except AppError as exc:
        failures += 1
        name = f"{settings.embedding_provider}:{settings.embedding_model}"
        print(f"FAIL embed  {name}  {exc} {exc.details}")
    print("All models verified." if not failures else f"{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
