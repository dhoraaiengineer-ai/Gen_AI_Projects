"""Live check of every configured LLM chain entry + the embedding model (ADR-008).

AGENT entries get a structured-output probe, ANSWER entries a short text probe, plus one embedding call.
Prints a pass/fail table only — never keys or URLs with credentials. Exit code 1 if any primary entry fails.

Usage (from autoserve-server/):  uv run python -m scripts.check_models
"""

from __future__ import annotations

import asyncio
import sys
import time

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel

from app.core.config import ChainEntry, Settings, get_settings


class Probe(BaseModel):
    ok: bool
    word: str


def _client(settings: Settings, entry: ChainEntry) -> ChatOpenAI:
    base_url, key = settings.provider_credentials(entry.provider)
    if key is None:
        raise RuntimeError(f"no API key for provider {entry.provider}")
    return ChatOpenAI(
        model=entry.model,
        base_url=base_url,
        api_key=key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_s,
        max_retries=0,
    )


async def probe_agent(settings: Settings, entry: ChainEntry) -> str:
    llm = _client(settings, entry).with_structured_output(Probe)
    out = await llm.ainvoke("Return ok=true and word='ready'.")
    if not isinstance(out, Probe) or not out.ok:
        raise RuntimeError(f"unexpected structured output: {out!r}")
    return "structured ok"


async def probe_answer(settings: Settings, entry: ChainEntry) -> str:
    out = await _client(settings, entry).ainvoke("Reply with the single word: ready")
    text = str(out.content).strip()
    if not text:
        raise RuntimeError("empty response")
    return f"text ok ({len(text)} chars)"


async def probe_embedding(settings: Settings) -> str:
    base_url, key = settings.provider_credentials("euri")
    emb = OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_base=base_url,
        openai_api_key=key,
        dimensions=settings.embedding_dimensions,
    )
    vec = await emb.aembed_query("synthetic veloxa test sentence")
    if len(vec) != settings.embedding_dimensions:
        raise RuntimeError(f"got {len(vec)} dims, expected {settings.embedding_dimensions}")
    return f"{len(vec)} dims"


async def _timed(label: str, coro: object) -> tuple[str, bool, str, float]:
    started = time.perf_counter()
    try:
        detail = await coro  # type: ignore[misc]
        return label, True, str(detail), time.perf_counter() - started
    except Exception as exc:
        return label, False, f"{type(exc).__name__}: {str(exc)[:140]}", time.perf_counter() - started


async def main() -> int:
    s = get_settings()
    jobs = [_timed(f"AGENT[{i}] {e.provider}:{e.model}", probe_agent(s, e)) for i, e in enumerate(s.agent_chain)]
    jobs += [_timed(f"ANSWER[{i}] {e.provider}:{e.model}", probe_answer(s, e)) for i, e in enumerate(s.answer_chain)]
    jobs.append(_timed(f"EMBED euri:{s.embedding_model}", probe_embedding(s)))
    results = await asyncio.gather(*jobs)
    width = max(len(r[0]) for r in results)
    for label, ok, detail, secs in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label.ljust(width)}  {secs:5.1f}s  {detail}")
    primaries_ok = all(ok for label, ok, _, _ in results if "[0]" in label or label.startswith("EMBED"))
    print("\nprimary entries + embeddings:", "OK" if primaries_ok else "FAILED")
    return 0 if primaries_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
