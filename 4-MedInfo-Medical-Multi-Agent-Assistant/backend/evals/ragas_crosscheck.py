"""Independent cross-check of the in-app RAGAS-style metrics with the real `ragas` library.

Runs in its OWN environment (.venv-ragas) because ragas pins openai/langchain versions that conflict with
the app's. It never imports the app: it reads a finished run file (evals/runs/eval_*.json, field
`ragas_inputs`, SYNTHETIC data only) and the provider keys from the repo .env (values never printed).

    ..\\.venv-ragas\\Scripts\\python evals/ragas_crosscheck.py                 # latest run, estimate only
    ..\\.venv-ragas\\Scripts\\python evals/ragas_crosscheck.py --limit 5 --yes # score 5 items

Results are "offline evaluation on a synthetic test set"; they say nothing about clinical performance.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LABEL = "offline evaluation on a synthetic test set"
METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
DEFAULT_BASE = {"groq": "https://api.groq.com/openai/v1", "euri": "https://api.euron.one/api/v1/euri"}


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, help="run file (default: latest evals/runs/eval_*.json with answers)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--judge", default="groq:openai/gpt-oss-120b", help="provider:model for the ragas judge")
    ap.add_argument("--yes", action="store_true", help="actually make the model calls")
    ap.add_argument(
        "--metrics", default=",".join(METRICS), help="comma list; results merge into the output file"
    )
    args = ap.parse_args()
    chosen = [m.strip() for m in args.metrics.split(",") if m.strip()]
    if not set(chosen) <= set(METRICS):
        ap.error(f"metrics must be among {METRICS}")

    runs = sorted((HERE / "runs").glob("eval_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    candidates = [args.run] if args.run else runs
    run_path = next(
        (p for p in candidates if json.loads(p.read_text(encoding="utf-8")).get("ragas_inputs")), None
    )
    if run_path is None:
        raise SystemExit("no run file with ragas_inputs; run evals.run_eval --answers --yes first")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    rows = [r for r in run["ragas_inputs"] if r["answer"].strip() and r["contexts"]]
    rows = rows[: args.limit] if args.limit else rows
    # ragas legacy metrics: faithfulness ~2 calls, relevancy 1 (+ embeddings), precision 1 per context, recall 1.
    per = {"faithfulness": lambda r: 2, "answer_relevancy": lambda r: 1}
    per |= {"context_precision": lambda r: len(r["contexts"]), "context_recall": lambda r: 1}
    est = sum(per[m](r) for r in rows for m in chosen)
    n_emb = len(rows) * 4 if "answer_relevancy" in chosen else 0
    print(
        f"Run: {run_path.name} | items with an answer: {len(rows)} | metrics: {', '.join(chosen)} | "
        f"estimated ~{est} chat + ~{n_emb} embedding calls"
    )
    if not args.yes:
        print("Estimate only. Re-run with --yes to make these calls.")
        return 0

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    env = read_env(REPO / ".env")
    provider, model = args.judge.split(":", 1)
    up = provider.upper()
    llm = ChatOpenAI(
        model=model,
        base_url=env.get(f"{up}_BASE_URL") or DEFAULT_BASE[provider],
        api_key=env[f"{up}_API_KEY"],
        temperature=0,
        max_retries=6,
    )
    emb = OpenAIEmbeddings(
        model=env.get("EMBEDDING_MODEL", "text-embedding-3-small"),
        base_url=env.get("EURI_BASE_URL") or DEFAULT_BASE["euri"],
        api_key=env["EURI_API_KEY"],
        check_embedding_ctx_length=False,
    )
    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": r["question"],
                "response": r["answer"],
                "retrieved_contexts": r["contexts"],
                "reference": r["reference"],
            }
            for r in rows
        ]
    )
    available = {
        "faithfulness": Faithfulness(),
        # strictness=1: one generated question per answer (Groq rejects n > 1 completions per request).
        "answer_relevancy": ResponseRelevancy(strictness=1),
        "context_precision": LLMContextPrecisionWithReference(),
        "context_recall": LLMContextRecall(),
    }
    result = evaluate(
        dataset,
        metrics=[available[m] for m in chosen],
        llm=LangchainLLMWrapper(llm),
        embeddings=LangchainEmbeddingsWrapper(emb),
        run_config=RunConfig(max_workers=2, timeout=180, max_retries=6),
        raise_exceptions=False,
    )
    df = result.to_pandas()
    rename = {"llm_context_precision_with_reference": "context_precision"}
    df = df.rename(columns=rename)

    ids = [r["id"] for r in rows]
    in_app = {i["id"]: dict(i["metrics"]) for i in run["items"] if i.get("mode") == "answers"}
    rejudged = run_path.with_name(run_path.stem + "_rejudged.json")
    if rejudged.exists():  # corrected judge scores (see that file's "reason") replace the first-run values
        for item in json.loads(rejudged.read_text(encoding="utf-8"))["items"]:
            in_app.setdefault(item["id"], {}).update(item["new"])

    out_path = run_path.with_name(run_path.stem + "_ragas.json")
    previous = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    per_item: dict[str, dict[str, float | None]] = {
        row["id"]: row for row in previous.get("per_item", []) if "id" in row
    }
    for item_id, record in zip(ids, df.to_dict(orient="records"), strict=True):
        row = per_item.setdefault(item_id, {"id": item_id})
        for metric in chosen:
            value = record.get(metric)
            row[metric] = None if value is None or value != value else round(float(value), 4)

    comparison: dict[str, dict[str, float | int | None]] = {}
    for metric in METRICS:
        # Paired: only items that BOTH ragas and the in-app judge scored.
        pairs = [
            (per_item[i][metric], in_app[i][metric])
            for i in ids
            if per_item.get(i, {}).get(metric) is not None and metric in in_app.get(i, {})
        ]
        comparison[metric] = {
            "ragas_library": round(mean(p[0] for p in pairs), 4) if pairs else None,
            "in_app": round(mean(p[1] for p in pairs), 4) if pairs else None,
            "paired_items": len(pairs),
        }
    out = {
        "label": LABEL,
        "source_run": run_path.name,
        "judge": args.judge,
        "items": ids,
        "comparison": comparison,
        "per_item": list(per_item.values()),
    }
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{LABEL} - {len(ids)} items, judge {args.judge}")
    print(f"{'metric':20} {'ragas library':>14} {'in-app':>8} {'paired':>7}")
    for metric, row in comparison.items():
        print(f"{metric:20} {row['ragas_library']!s:>14} {row['in_app']!s:>8} {row['paired_items']:>7}")
    print(f"Saved {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
