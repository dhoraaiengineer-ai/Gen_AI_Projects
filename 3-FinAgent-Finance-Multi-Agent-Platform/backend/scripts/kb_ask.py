"""Ask the knowledge base (grounded answer with citations) or evaluate retrieval on the golden set.

    uv run python -m scripts.kb_ask "What is the 1-day 95% VaR budget?"
    uv run python -m scripts.kb_ask "..." --role analyst --search-only
    uv run python -m scripts.kb_ask --golden            # Recall@5 / MRR, no LLM calls

Cost: one embedding call per question, plus one LLM call (~1.5k tokens) unless --search-only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.config.settings import REPO_ROOT, get_settings
from src.container import Container
from src.core.domain import Role
from src.core.logging import configure_logging
from src.core.tenancy import DEMO_TENANT_ID, tenant_scope


async def golden(container: Container) -> int:
    items = json.loads((REPO_ROOT / "knowledge" / "golden_qa.json").read_text(encoding="utf-8"))
    kb = container.knowledge
    hits, rr, n = 0, 0.0, 0
    for item in items["items"]:
        if item.get("refusal"):
            continue
        n += 1
        result = await kb.search(item["question"], kb.filters(Role.ADMIN), k=5)
        sources = [h.source for h in result.hits]
        rank = sources.index(item["source"]) + 1 if item["source"] in sources else None
        hits += rank is not None
        rr += 1 / rank if rank else 0.0
        print(
            f"{item['id']} rank={rank or '-':>2} reranker={result.reranker:13s} {item['question']}"
        )
    print(f"\nRecall@5 = {hits / n:.2f}   MRR = {rr / n:.2f}   ({n} questions)")
    return 0


async def run(args: argparse.Namespace) -> int:
    container = Container.build(get_settings())
    try:
        with tenant_scope(DEMO_TENANT_ID):
            if args.golden:
                return await golden(container)
            kb = container.knowledge
            filters = kb.filters(Role(args.role))
            if args.search_only:
                result = await kb.search(args.question, filters, k=5)
                print(json.dumps(result.as_dict(), indent=2, default=str))
                return 0
            answer = await kb.ask(args.question, filters)
            print(f"\n{answer['answer']}\n")
            for c in answer["citations"]:
                print(f"  [{c['n']}] {c['citation']}  (score {c['relevanceScore']})")
            meta = answer["retrieval"]
            print(
                f"\nsource={answer['answerSource']} reranker={meta['reranker']} "
                f"kb_version={answer['kbVersion']} redactions={answer['redactions']}"
            )
            return 0
    finally:
        await container.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default="What is the 1-day 95% VaR budget?")
    parser.add_argument("--role", default="risk_manager", choices=[r.value for r in Role])
    parser.add_argument("--search-only", action="store_true")
    parser.add_argument("--golden", action="store_true")
    args = parser.parse_args()
    configure_logging()
    sys.exit(asyncio.run(run(args), loop_factory=asyncio.SelectorEventLoop))


if __name__ == "__main__":
    main()
