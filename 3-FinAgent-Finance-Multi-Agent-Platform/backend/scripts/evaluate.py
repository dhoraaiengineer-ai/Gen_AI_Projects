"""Run evaluation suites, save results to evaluation/results/ and log them to MLflow.

    uv run python -m scripts.evaluate                          # offline: routing (keywords) + chunking
    uv run python -m scripts.evaluate --suite rag              # retrieval only (13 embedding calls)
    uv run python -m scripts.evaluate --suite rag --answers --judge   # + answers and LLM judge
    uv run python -m scripts.evaluate --suite routing --live   # Jev/LLM routing (1 LLM call each)
    uv run python -m scripts.evaluate --suite tools            # deterministic agents on the DB
    uv run python -m scripts.evaluate --suite tools --live     # agents with LLM tool loops

Cost (live, approx.): routing 32 calls / ~8k tokens · rag answers 13 calls / ~20k tokens, judge
+12 calls / ~25k · tools --live ~45 calls / ~45k tokens. Offline suites make no network calls;
``--suite tools`` without ``--live`` uses the database and one RAG answer call.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

from src.config.settings import BACKEND_ROOT, REPO_ROOT, get_settings
from src.core.decisions import DecisionService
from src.core.logging import configure_logging
from src.core.tenancy import DEMO_TENANT_ID, tenant_scope
from src.evaluation.suites import (
    JudgeScore,
    chunking_suite,
    load_golden,
    rag_suite,
    routing_suite,
    tools_suite,
)
from src.orchestration.routing import PortfolioRef, Router
from src.orchestration.runner import Caller
from src.rag.chunking import STRATEGIES
from src.rag.loaders import load_bytes
from src.rag.types import DocumentMeta

RESULTS = REPO_ROOT / "evaluation" / "results"
PORTFOLIOS = [
    PortfolioRef("PF-A", "Portfolio A — Technology Growth"),
    PortfolioRef("PF-B", "Portfolio B — Balanced Multi-Asset"),
    PortfolioRef("PF-C", "Portfolio C — Dividend Income"),
]
JUDGE_PROMPT = (
    "You grade answers from a document question-answering system for an asset manager. Score "
    "faithfulness (every claim supported by the context; 5 = fully supported) and relevance (the "
    "answer addresses the question; 5 = fully). A correct refusal when the context lacks the answer "
    "is faithful. Give a one-sentence reason."
)


class _NoOcr:
    def available(self) -> bool:
        return False

    def image_text(self, data: bytes) -> str:
        raise RuntimeError("OCR disabled for evaluation")

    def pdf_page_text(self, data: bytes, page_index: int) -> str:
        raise RuntimeError("OCR disabled for evaluation")


def _container(live: bool) -> Any:
    from src.container import Container  # noqa: PLC0415 - heavy import only when needed

    settings = get_settings()
    if not live:  # no LLM anywhere in agents/routing/narrative (RAG answers still use the chain)
        settings = settings.model_copy(
            update={
                "agent_llm_tool_loop": False,
                "llm_narrative": False,
                "llm_routing": False,
                "typesafe_api_key": None,
            }
        )
    return Container.build(settings)


async def run_routing(live: bool) -> dict[str, Any]:
    items = load_golden("routing")
    if not live:
        return await routing_suite(Router(DecisionService(None)), items, PORTFOLIOS)
    container = _container(True)
    try:
        with tenant_scope(DEMO_TENANT_ID):
            return await routing_suite(await container.router(), items, PORTFOLIOS)
    finally:
        await container.aclose()


def run_chunking() -> dict[str, Any]:
    from src.providers.tokenizer import token_counter  # noqa: PLC0415

    manifest = json.loads((REPO_ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8"))
    corpus = {}
    for path in sorted((REPO_ROOT / "knowledge" / "samples").iterdir()):
        raw = manifest.get(path.name, {})
        meta = DocumentMeta(
            doc_type=str(raw.get("doc_type", "internal")),
            classification=str(raw.get("classification", "internal")),
            ticker=raw.get("ticker"),
            fiscal_period=raw.get("fiscal_period"),
        )
        corpus[path.name] = (load_bytes(path.read_bytes(), path.name, _NoOcr()), meta)
    return chunking_suite(corpus, load_golden("rag"), STRATEGIES, count=token_counter())


async def run_rag(answers: bool, judge: bool) -> dict[str, Any]:
    container = _container(True)
    s = container.settings
    try:
        judge_fn = None
        if judge:
            model = container.llm.structured_model(JudgeScore, chain="answer", max_tokens=200)

            async def judge_fn(question: str, context: str, answer: str) -> JudgeScore | None:
                try:
                    result: JudgeScore = await model.ainvoke(
                        [
                            ("system", JUDGE_PROMPT),
                            (
                                "human",
                                f"Question: {question}\n\nContext:\n{context}\n\nAnswer: {answer}",
                            ),
                        ]
                    )
                    return result
                except Exception as exc:  # a failed judge call must not fail the suite
                    print(f"  judge failed: {type(exc).__name__}", file=sys.stderr)
                    return None

        with tenant_scope(DEMO_TENANT_ID):
            result = await rag_suite(
                container.knowledge, load_golden("rag"), answers=answers, judge=judge_fn
            )
        result["config"] = {
            "reranker": s.reranker,
            "embedding": f"{s.embedding_provider}:{s.embedding_model}",
        }
        return result
    finally:
        await container.aclose()


async def run_tools(live: bool) -> dict[str, Any]:
    container = _container(live)
    try:
        await container.warm_up()  # as the API does at startup: no cold-load timeouts
        with tenant_scope(DEMO_TENANT_ID):
            runner = await container.build_runner(persist_approvals=False)

            async def run(question: str, role: str) -> dict[str, Any]:
                caller = Caller(tenant_id=str(DEMO_TENANT_ID), role=role, user_id=None)
                report: dict[str, Any] = await runner.run(question, caller)
                return report

            return await tools_suite(run, load_golden("tools"))
    finally:
        await container.aclose()


def save_and_log(suite: str, result: dict[str, Any], params: dict[str, Any], mlflow: bool) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{suite}.json"
    payload = {"suite": suite, "params": params, "at": time.strftime("%Y-%m-%dT%H:%M:%S")} | result
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\n[{suite}] " + "  ".join(f"{k}={v}" for k, v in result["metrics"].items()))
    for name, values in result.get("strategies", {}).items():
        print(f"  {name:16s} {values}")
    for row in result.get("items", []):
        flag = row.get("correct", row.get("rank", row.get("tool_recall")))
        if row.get("refusal"):
            flag = row.get("refused")  # refusal items have no rank; a correct refusal passes
        failed = "failed" in row.get("status", [])
        if flag in (False, None, 0, 0.0) or row.get("missing_tools") or failed:
            print(f"  ✗ {row}")
    print(f"  saved {path.relative_to(REPO_ROOT)}")
    if mlflow:
        from src.evaluation.tracking import log_suite  # noqa: PLC0415
        from src.ml.registry import tracking_uri_for  # noqa: PLC0415

        uri = tracking_uri_for(get_settings().mlflow_url, BACKEND_ROOT)
        print(f"  mlflow run {log_suite(uri, suite, result, params, path)}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows console
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--suite", choices=["routing", "chunking", "rag", "tools", "offline"], default="offline"
    )
    parser.add_argument("--live", action="store_true", help="use the LLM chains (spends quota)")
    parser.add_argument("--answers", action="store_true", help="rag: also generate answers")
    parser.add_argument(
        "--judge", action="store_true", help="rag: LLM-as-judge (implies --answers)"
    )
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()
    configure_logging("WARNING")
    mlflow = not args.no_mlflow
    loop = asyncio.SelectorEventLoop
    suites = ["routing", "chunking"] if args.suite == "offline" else [args.suite]
    for suite in suites:
        params = {"live": args.live, "answers": args.answers or args.judge, "judge": args.judge}
        if suite == "routing":
            result = asyncio.run(run_routing(args.live), loop_factory=loop)
        elif suite == "chunking":
            result = run_chunking()
        elif suite == "rag":
            result = asyncio.run(run_rag(args.answers or args.judge, args.judge), loop_factory=loop)
        else:
            result = asyncio.run(run_tools(args.live), loop_factory=loop)
        save_and_log(suite if not args.live else f"{suite}-live", result, params, mlflow)
    return 0


if __name__ == "__main__":
    sys.exit(main())
