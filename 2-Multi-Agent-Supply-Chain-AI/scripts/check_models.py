"""Live check of every configured model (small, cheap calls).

- answer chain: one short completion each
- agent chain: a full tool-call round trip each (call → tool result → final answer); a model that fails this
  must not be in LLM_AGENT_CHAIN
- embeddings: one vector, dimension check

    uv run python scripts/check_models.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.core.circuit_breaker import BreakerRegistry
from app.core.config import get_settings
from app.rag.providers import LlmFactory, ResilientEmbeddings


@tool
def get_inventory(sku: str) -> dict[str, object]:
    """Return the current available stock for a SKU."""
    return {"sku": sku, "available": 1650, "days_of_cover": 4.1}


async def check_answer(factory: LlmFactory, spec: object) -> str:
    llm = factory.chat(spec, max_tokens=300)  # type: ignore[arg-type]
    t = time.perf_counter()
    out = await llm.ainvoke([HumanMessage("Reply with exactly the word: OK")])
    return f"{str(out.content).strip()[:20]!r} in {time.perf_counter() - t:.1f}s"


async def check_round_trip(factory: LlmFactory, spec: object) -> str:
    llm = factory.chat(spec, max_tokens=400).bind_tools([get_inventory])  # type: ignore[arg-type]
    t = time.perf_counter()
    messages: list = [HumanMessage("How many units of SKU-100 are available? Use the tool, then answer in one sentence.")]
    first = await llm.ainvoke(messages)
    if not first.tool_calls:
        return "FAIL: no tool call"
    messages.append(first)
    for call in first.tool_calls:
        messages.append(ToolMessage(content=str(get_inventory.invoke(call["args"])), tool_call_id=call["id"]))
    final = await llm.ainvoke(messages)
    ok = "1650" in str(final.content).replace(",", "")
    return f"{'PASS' if ok else 'CHECK'} {str(final.content).strip()[:80]!r} in {time.perf_counter() - t:.1f}s"


async def main() -> None:
    s = get_settings()
    factory = LlmFactory(s, BreakerRegistry(99, 1))
    print("== answer chain")
    for spec in s.answer_chain:
        try:
            print(f"  {spec}: {await check_answer(factory, spec)}")
        except Exception as exc:
            print(f"  {spec}: ERROR {type(exc).__name__}: {str(exc)[:160]}")
    print("== agent chain (tool-call round trip)")
    for spec in s.agent_chain:
        try:
            print(f"  {spec}: {await check_round_trip(factory, spec)}")
        except Exception as exc:
            print(f"  {spec}: ERROR {type(exc).__name__}: {str(exc)[:160]}")
    print("== embeddings")
    try:
        emb = ResilientEmbeddings(s)
        v = await emb.embed_query("lithium battery lead time")
        print(f"  {s.embedding_model}: {len(v)} dims")
    except Exception as exc:
        print(f"  {s.embedding_model}: ERROR {type(exc).__name__}: {str(exc)[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
