"""Evaluation runner. Logs every run to MLflow (when installed - use the separate .venv-eval) and always
writes a JSON report to evals/runs/. Runs OUTSIDE the API container.

Modes (combine freely):
  --retrieval   evidence hit rate @k and MRR on the golden set (embeddings + re-ranker only; cheap)
  --answers     full answers + LLM judge (correctness, citation accuracy) + RAGAS-style metrics
  --safety      the release-blocking safety suite (exit code 1 if any set is below its threshold)
Options:
  --limit N     only the first N golden items      --no-rerank   retrieval without the LLM re-ranker
  --to-review   queue the evaluated answers for clinician review
  --yes         actually make the (quota-spending) model calls; without it only the estimate is printed

Results are offline evaluation on a SYNTHETIC test set, not clinical performance.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import PROJECT_ROOT, get_settings, parse_chain
from app.container import build_chat_model, build_container
from app.core.logging import configure_logging
from app.rag.evaluation import (
    EvalJudge,
    EvalRun,
    GoldenSet,
    ItemResult,
    context_precision,
    evidence_rank,
    summarise,
)
from app.rag.gateway import LLMGateway
from app.rag.interfaces import ChatModel, Passage, SearchFilter
from app.safety.evaluation import SafetySuite

EVALS = PROJECT_ROOT / "evals"
LABEL = "offline evaluation on a synthetic test set"


class Recording:
    """Wraps the model so the safety suite can check that no PHI reached any prompt."""

    def __init__(self, inner: ChatModel) -> None:
        self._inner = inner
        self.name = inner.name
        self.prompts: list[str] = []

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        self.prompts.append(f"{system}\n{user}")
        return self._inner.complete(system, user, temperature=temperature, max_tokens=max_tokens)


def estimate(args: argparse.Namespace, n_items: int, n_ooc: int, suite: SafetySuite) -> dict[str, int]:
    rerank = 0 if args.no_rerank else 1
    calls = {"embedding": 0, "chat": 0}
    if args.retrieval:
        calls["embedding"] += n_items
        calls["chat"] += n_items * rerank
    if args.answers:  # triage + scope + rerank + answer (+judge on high-risk) + 5 eval-judge calls
        calls["embedding"] += n_items
        calls["chat"] += n_items * (4 + 1 + 5)
    if args.safety:
        d = suite.data
        n = len(d["emergency"]) + len(d["dosing"]) + len(d["diagnosis"]) + len(d["injection"]["questions"])
        n += len(d["injection"].get("uploads", [])) + 1 + n_ooc
        calls["embedding"] += n
        calls["chat"] += n * 4
    return calls


def git_sha() -> str:
    try:
        git = shutil.which("git")
        if git is None:
            return "unknown"
        return subprocess.run(  # noqa: S603 - fixed argv, resolved executable
            [git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    for flag in ("retrieval", "answers", "safety", "no-rerank", "to-review", "yes"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--judge-chain",
        default="",
        help="model chain for the evaluation judge, e.g. groq:openai/gpt-oss-120b (default: the answer chain). "
        "A judge from a different model family avoids grading its own answers.",
    )
    args = ap.parse_args()
    if not (args.retrieval or args.answers or args.safety):
        ap.error("choose at least one of --retrieval, --answers, --safety")

    settings = get_settings()
    if args.no_rerank:
        settings = settings.model_copy(update={"rerank_enabled": False})
    configure_logging("WARNING", "text")
    golden = GoldenSet.load(EVALS / "golden.yaml")
    items = list(golden.items[: args.limit] if args.limit else golden.items)
    suite = SafetySuite.load(EVALS / "safety_suite.yaml", PROJECT_ROOT / "data" / "synthetic" / "uploads")

    est = estimate(args, len(items), len(golden.out_of_corpus), suite)
    print(
        f"Estimated live calls: ~{est['chat']} chat + ~{est['embedding']} embedding (model: {settings.answer_chain()[0].label})"
    )
    if not args.yes:
        print("Dry run only. Re-run with --yes to make these calls.")
        return 0

    model = Recording(build_chat_model(settings))
    container = build_container(settings, model=model, classifier=model)
    judge_model: ChatModel = (
        build_chat_model(settings, chain=parse_chain(args.judge_chain)) if args.judge_chain else model
    )
    judge = EvalJudge(LLMGateway({"fast": judge_model, "quality": judge_model}).for_task("eval_judge"))
    k = settings.retrieval_top_k
    run: dict[str, Any] = {
        "label": LABEL,
        "params": {
            "answer_model": settings.answer_chain()[0].label,
            "judge_model": judge_model.name,
            "embedding_model": settings.embedding_model,
            "top_k": k,
            "rerank": settings.rerank_enabled,
            "chunk_strategy": settings.chunk_strategy,
            "golden_version": golden.version,
            "items": len(items),
            "git_sha": git_sha(),
        },
        "metrics": {},
        "items": [],
        "ragas_inputs": [],
    }
    started = time.time()

    if args.retrieval:
        results = []
        for it in items:
            passages = container.retriever.retrieve(it.question, k, SearchFilter(trusted_only=True))
            results.append(ItemResult(it.id, it.question, it.category, evidence_rank(it.evidence, passages)))
        run["metrics"].update({f"retrieval_{key}": v for key, v in summarise(results, k).items()})
        run["items"] += [{"mode": "retrieval", **asdict(r)} for r in results]

    if args.answers:
        results = []
        for it in items:
            ctx: list[Passage] = []
            ans = container.chat.answer(it.question, user_id="eval", capture=ctx)
            texts = [p.text for p in ctx]
            m = judge.correctness(it.question, ans.answer, list(it.facts), ctx)
            m["faithfulness"] = judge.faithfulness(ans.answer, texts)
            m["answer_relevancy"] = judge.answer_relevancy(it.question, ans.answer or " ".join(ans.preface))
            m["context_precision"] = context_precision(judge.context_relevance(it.question, texts))
            m["context_recall"] = judge.context_recall(list(it.facts), texts)
            results.append(
                ItemResult(
                    it.id, it.question, it.category, evidence_rank(it.evidence, ctx), ans.kind, ans.answer, m
                )
            )
            # SYNTHETIC inputs kept for the independent RAGAS cross-check (evals/ragas_crosscheck.py).
            run["ragas_inputs"].append(
                {
                    "id": it.id,
                    "question": it.question,
                    "answer": ans.answer,
                    "contexts": texts,
                    "reference": " ".join(it.facts),
                }
            )
            if args.to_review:
                container.review.enqueue(it.question, ans, source="eval")
        run["metrics"].update({f"answer_{key}": v for key, v in summarise(results, k).items()})
        run["metrics"]["answer_judge_errors"] = judge.errors  # each failed judge call scored 0
        run["items"] += [{"mode": "answers", **asdict(r)} for r in results]

    safety_ok = True
    if args.safety:
        report = suite.run(
            container.chat,
            ingest=container.ingest,
            out_of_corpus=list(golden.out_of_corpus),
            sent_prompts=lambda: model.prompts,
            stored_text=lambda cid: json.dumps(
                [m.text for m in container.memory.messages(cid, "safety-eval")]
            ),
        )
        safety_ok = report.passed
        run["metrics"].update({f"safety_{name}": rate for name, rate in report.rates.items()})
        run["metrics"]["safety_passed"] = 1.0 if safety_ok else 0.0
        run["items"] += [{"mode": "safety", **asdict(r)} for r in report.results]

    run["metrics"]["duration_s"] = round(time.time() - started, 1)
    out_dir = EVALS / "runs"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")

    try:
        import mlflow  # only in .venv-eval

        mlflow.set_experiment("medinfo-eval")
        with mlflow.start_run(run_name=out.stem):
            mlflow.set_tag("label", LABEL)
            mlflow.log_params(run["params"])
            mlflow.log_metrics({k_: float(v) for k_, v in run["metrics"].items()})
            mlflow.log_artifact(str(out))
        print("Logged to MLflow experiment 'medinfo-eval'.")
    except ImportError:
        print("MLflow not installed in this environment; JSON report only (use .venv-eval for MLflow).")

    import uuid

    container.eval_runs.add(
        EvalRun(
            id=uuid.uuid4().hex,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            label=LABEL,
            params=run["params"],
            metrics=run["metrics"],
        )
    )
    print(json.dumps({"label": LABEL, "metrics": run["metrics"]}, indent=2))
    print(f"Report: {out}")
    if args.safety and not safety_ok:
        print("SAFETY SUITE FAILED - release blocked.")
        return 1
    return 0


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.WARNING)
    sys.exit(main())
