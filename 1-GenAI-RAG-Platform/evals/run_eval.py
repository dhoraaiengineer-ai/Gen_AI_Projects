"""Run the golden-dataset evaluation and log it to MLflow.

Every run records:
  params    collection, models and fallback chains, embedding model, chunking, top_k, hybrid search,
            re-ranking, temperature, hallucination guard, number of questions
  metrics   retrieval (evidence hit rate, source hit rate, MRR), LLM-as-judge (answer accuracy, citation
            accuracy, grounded rate) and RAGAS (faithfulness, answer relevancy, context precision/recall)
  artifacts eval_items.json (every question with its answer, verdicts and scores)

Usage (app venv, needs .env like the API):
    .venv/Scripts/python -m evals.run_eval --limit 10                 # judged run, all RAGAS metrics
    .venv/Scripts/python -m evals.run_eval --no-judge                 # retrieval metrics only, no LLM calls
    .venv/Scripts/python -m evals.run_eval --source faq.md --metrics faithfulness context_recall
    .venv/Scripts/mlflow ui --backend-store-uri sqlite:///mlflow.db   # then open http://localhost:5000

MLFLOW_TRACKING_URI overrides the local sqlite store (e.g. a shared MLflow server).
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from app.config import get_settings
from app.container import build_container
from app.rag.ragas_metrics import METRICS

logger = logging.getLogger("evals")

DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"
EXPERIMENT = "rag-evaluation"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=10, help="max golden questions (default 10)")
    parser.add_argument("--source", help="only this document's golden questions")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--no-judge", action="store_true", help="retrieval metrics only (no LLM calls)")
    parser.add_argument("--metrics", nargs="+", choices=METRICS, default=list(METRICS))
    parser.add_argument("--run-name", default=None)
    return parser.parse_args(argv)


def run_params(settings, args: argparse.Namespace, count: int) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "collection": settings.collection_name,
        "llm_model": settings.llm_model,
        "llm_fallbacks": ",".join(
            [f"{settings.llm_fallback_provider}:{settings.llm_fallback_model}", settings.llm_extra_fallbacks]
        ),
        "eval_judge_model": settings.eval_judge_model or settings.llm_model,
        "embedding": f"{settings.embedding_provider}:{settings.embedding_model}",
        "chunking": settings.chunking_strategy.value,
        "chunk_size": settings.chunk_size,
        "top_k": args.top_k or settings.top_k,
        "hybrid_search": settings.hybrid_search,
        "rerank": settings.rerank_enabled,
        "temperature": settings.llm_temperature,
        "hallucination_guard": settings.hallucination_guard,
        "judged": not args.no_judge,
        "ragas_metrics": ",".join(args.metrics) if not args.no_judge else "",
        "questions": count,
        "source_filter": args.source or "all",
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    import mlflow  # heavy import: only when the job actually runs

    args = parse_args(argv)
    settings = get_settings()
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI))
    mlflow.set_experiment(EXPERIMENT)

    container = build_container(settings)
    try:
        report = container.service.evaluate(args.source, args.limit, args.top_k, not args.no_judge, args.metrics)
    finally:
        container.close()
    if not report.count:
        logger.error("no golden questions found (import data/golden/*.json or upload documents first)")
        return 1

    metrics = {
        name: value
        for name, value in report.model_dump(exclude={"items", "count", "top_k", "judged"}).items()
        if isinstance(value, int | float)
    }
    with mlflow.start_run(run_name=args.run_name) as run:
        mlflow.log_params(run_params(settings, args, report.count))
        mlflow.log_metrics(metrics)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval_items.json"
            path.write_text(json.dumps([i.model_dump() for i in report.items], indent=2), encoding="utf-8")
            mlflow.log_artifact(str(path))
        logger.info("logged MLflow run %s", run.info.run_id)

    width = max(map(len, metrics))
    print(f"\n{report.count} questions, top {report.top_k}, judged={report.judged}")
    for name, value in metrics.items():
        print(f"  {name:<{width}}  {value:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
