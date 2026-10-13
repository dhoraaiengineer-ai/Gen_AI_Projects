"""Evaluation suites: routing, tool selection, RAG retrieval/answers and chunking strategies.

Each suite returns ``{"metrics": {...}, "items": [...]}`` so the runner can print, save and log
the same structure to MLflow. Suites receive their dependencies (router, runner, knowledge
service, loaded documents); nothing here reads settings or opens connections.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.config.settings import REPO_ROOT
from src.evaluation.metrics import (
    answer_relevancy,
    classification_report,
    context_precision,
    context_recall,
    faithfulness,
    first_rank,
    mean,
    mrr,
    ndcg_at_k,
    recall_at_k,
    set_scores,
)
from src.orchestration.routing import PortfolioRef, Router
from src.rag.answer import REFUSAL
from src.rag.chunking import ChunkingConfig, chunk_document
from src.rag.service import KnowledgeService
from src.rag.types import DocumentMeta, LoadedDocument, TokenCounter

EVAL_DIR = REPO_ROOT / "evaluation"
GOLDEN_RAG = REPO_ROOT / "knowledge" / "golden_qa.json"


def load_golden(name: str) -> list[dict[str, Any]]:
    path = GOLDEN_RAG if name == "rag" else EVAL_DIR / f"{name}_golden.json"
    items: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))["items"]
    return items


# ----------------------------------------------------------------------------- routing
async def routing_suite(
    router: Router, items: Sequence[dict[str, Any]], portfolios: list[PortfolioRef]
) -> dict[str, Any]:
    rows, pairs, entity_hits = [], [], []
    for item in items:
        started = time.perf_counter()
        result = await router.classify(item["question"], portfolios)
        acceptable = {item["intent"], *item.get("acceptable", [])}
        correct = result.intent in acceptable
        pairs.append((item["intent"], item["intent"] if correct else result.intent))
        if item.get("portfolio") or item.get("tickers"):
            entity_hits.append(
                (not item.get("portfolio") or result.portfolio_id == item["portfolio"])
                and set(item.get("tickers", [])) <= set(result.tickers)
            )
        rows.append(
            {
                "id": item["id"],
                "expected": item["intent"],
                "predicted": result.intent,
                "correct": correct,
                "method": result.method,
                "portfolio": result.portfolio_id,
                "tickers": result.tickers,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    report = classification_report(pairs)
    methods = Counter(r["method"] for r in rows)
    return {
        "metrics": {
            "routing_accuracy": round(report.accuracy, 3),
            "routing_macro_f1": round(report.macro_f1, 3),
            "entity_accuracy": round(mean(1.0 if h else 0.0 for h in entity_hits), 3),
            "n": len(rows),
        },
        "methods": dict(methods),
        "per_class": report.per_class,
        "confusion": report.confusion,
        "items": rows,
    }


# ----------------------------------------------------------------------------- tools
RunQuestion = Callable[[str, str], Awaitable[dict[str, Any]]]  # (question, role) → report


async def tools_suite(run: RunQuestion, items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for item in items:
        started = time.perf_counter()
        report = await run(item["question"], item["role"])
        agents = [a["name"] for a in report.get("agents", [])]
        tools = sorted({t for a in report.get("agents", []) for t in a.get("toolCalls", [])})
        agent_scores = set_scores(item["agents"], agents)
        tool_recall = set_scores(item["tools"], tools)["recall"]
        rows.append(
            {
                "id": item["id"],
                "intent": report.get("intent"),
                "agents": agents,
                "agent_f1": round(agent_scores["f1"], 3),
                "missing_tools": sorted(set(item["tools"]) - set(tools)),
                "tool_recall": round(tool_recall, 3),
                "tools_called": len(tools),
                "status": [a.get("status") for a in report.get("agents", [])],
                "seconds": round(time.perf_counter() - started, 1),
            }
        )
    return {
        "metrics": {
            "agent_selection_f1": round(mean(r["agent_f1"] for r in rows), 3),
            "required_tool_recall": round(mean(r["tool_recall"] for r in rows), 3),
            "exact_plan_rate": round(mean(1.0 if r["agent_f1"] == 1.0 else 0.0 for r in rows), 3),
            # selection can be right while an agent still fails (timeout, provider down)
            "agent_success_rate": round(
                mean(1.0 if all(st != "failed" for st in r["status"]) else 0.0 for r in rows), 3
            ),
            "n": len(rows),
        },
        "items": rows,
    }


# ----------------------------------------------------------------------------- RAG
class JudgeScore(BaseModel):
    """LLM-as-judge rubric (1 = poor … 5 = excellent)."""

    faithfulness: int = Field(ge=1, le=5, description="Every claim is supported by the context")
    relevance: int = Field(ge=1, le=5, description="The answer addresses the question")
    reason: str = Field(max_length=300)


Judge = Callable[[str, str, str], Awaitable[JudgeScore | None]]  # (question, context, answer)


async def rag_suite(
    kb: KnowledgeService,
    items: Sequence[dict[str, Any]],
    *,
    role: str = "admin",
    k: int = 5,
    answers: bool = False,
    judge: Judge | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    filters = kb.filters(role)
    for item in items:
        search = await kb.search(item["question"], filters, k=k)
        sources = [h.source for h in search.hits]
        contexts = [h.context for h in search.hits]
        row: dict[str, Any] = {"id": item["id"], "refusal": bool(item.get("refusal"))}
        if not item.get("refusal"):
            rank = first_rank(sources, item["source"])
            row |= {
                "rank": rank,
                "context_recall": context_recall(contexts, item["evidence"]),
                "context_precision": round(context_precision(sources, item["source"]), 3),
                "reranker": search.reranker,
            }
        if answers:
            result = await kb.ask(item["question"], filters, k=k)
            answer = str(result["answer"])
            documents = [h.context for h in search.hits]
            row |= {
                "answer_source": result["answerSource"],
                "refused": answer.strip() == REFUSAL,
                "faithfulness": round(faithfulness(answer, documents), 3),
                "answer_relevancy": answer_relevancy(answer, item.get("answer_contains", [])),
            }
            if judge is not None and not item.get("refusal"):
                score = await judge(item["question"], "\n\n".join(documents)[:6000], answer)
                if score is not None:
                    row |= {
                        "judge_faithfulness": score.faithfulness,
                        "judge_relevance": score.relevance,
                        "judge_reason": score.reason,
                    }
        rows.append(row)
    answerable = [r for r in rows if not r["refusal"]]
    ranks = [r["rank"] for r in answerable]
    metrics: dict[str, float] = {
        "recall_at_1": round(recall_at_k(ranks, 1), 3),
        f"recall_at_{k}": round(recall_at_k(ranks, k), 3),
        "mrr": round(mrr(ranks), 3),
        f"ndcg_at_{k}": round(ndcg_at_k(ranks, k), 3),
        "context_recall": round(mean(r["context_recall"] for r in answerable), 3),
        "context_precision": round(mean(r["context_precision"] for r in answerable), 3),
        "n": float(len(rows)),
    }
    if answers:
        refusals = [r for r in rows if r["refusal"]]
        metrics |= {
            "faithfulness": round(mean(r["faithfulness"] for r in answerable), 3),
            "answer_relevancy": round(mean(r["answer_relevancy"] for r in answerable), 3),
            "refusal_accuracy": round(
                mean(1.0 if r["refused"] == r["refusal"] else 0.0 for r in rows), 3
            ),
            "false_refusals": float(sum(1 for r in answerable if r["refused"])),
            "llm_answer_rate": round(
                mean(1.0 if r["answer_source"] == "llm" else 0.0 for r in answerable), 3
            ),
        }
        if refusals:
            metrics["correct_refusals"] = float(sum(1 for r in refusals if r["refused"]))
        judged = [r for r in answerable if "judge_faithfulness" in r]
        if judged:
            metrics |= {
                "judge_faithfulness": round(mean(r["judge_faithfulness"] for r in judged), 2),
                "judge_relevance": round(mean(r["judge_relevance"] for r in judged), 2),
            }
    return {"metrics": metrics, "items": rows}


# ----------------------------------------------------------------------------- chunking
_WORD = re.compile(r"[a-z0-9]+(?:[.%][0-9]+)?%?")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _bm25_rank(query: str, texts: Sequence[str], k1: float = 1.2, b: float = 0.75) -> list[int]:
    docs = [Counter(_tokens(t)) for t in texts]
    n = len(docs)
    avg = mean(sum(d.values()) for d in docs) or 1.0
    df = Counter(term for d in docs for term in d)
    terms = set(_tokens(query))
    scores = []
    for i, d in enumerate(docs):
        length = sum(d.values()) or 1
        score = 0.0
        for term in terms:
            tf = d.get(term, 0)
            if tf:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg))
        scores.append((score, i))
    return [i for s, i in sorted(scores, reverse=True) if s > 0]


def chunking_suite(
    corpus: dict[str, tuple[LoadedDocument, DocumentMeta]],
    items: Sequence[dict[str, Any]],
    strategies: Sequence[str],
    *,
    count: TokenCounter,
    k: int = 5,
) -> dict[str, Any]:
    """Compare chunkers under the same lexical retriever (BM25 over each strategy's chunks; no
    embeddings or LLM calls). A hit = the golden evidence sentence is inside a top-k context."""
    answerable = [i for i in items if not i.get("refusal")]
    results: dict[str, dict[str, Any]] = {}
    for strategy in strategies:
        texts, contexts, sources, tokens = [], [], [], []
        try:
            for name, (doc, meta) in corpus.items():
                chunks = chunk_document(
                    doc, meta, name, strategy=strategy, config=ChunkingConfig(), count=count
                )
                parents = {c.id: c.content for c in chunks if not c.embed}
                for c in chunks:
                    if not c.embed:
                        continue
                    texts.append(c.embed_text)
                    contexts.append(
                        str(c.location.get("context") or parents.get(c.parent_id or "", c.content))
                    )
                    sources.append(name)
                    tokens.append(c.token_count)
        except Exception as exc:  # strategies needing models (semantic, proposition) are skipped
            results[strategy] = {"skipped": f"{type(exc).__name__}: {str(exc)[:120]}"}
            continue
        ranks, recalls = [], []
        for item in answerable:
            order = _bm25_rank(item["question"], texts)[:k]
            ranks.append(first_rank([sources[i] for i in order], item["source"]))
            recalls.append(context_recall([contexts[i] for i in order], item["evidence"]))
        results[strategy] = {
            "chunks": len(texts),
            "avg_tokens": round(mean(tokens), 1),
            f"source_recall_at_{k}": round(recall_at_k(ranks, k), 3),
            "mrr": round(mrr(ranks), 3),
            f"evidence_recall_at_{k}": round(mean(recalls), 3),
        }
    scored = {s: r for s, r in results.items() if "skipped" not in r}
    key = f"evidence_recall_at_{k}"
    best = max(scored, key=lambda s: (scored[s][key], scored[s]["mrr"]), default=None)
    return {
        "metrics": {
            "best_strategy": best,
            f"best_{key}": scored[best][key] if best else 0.0,
            "n": len(answerable),
        },
        "strategies": results,
    }
