"""Knowledge-base MCP tools (research server): document search, hybrid/vector search, re-ranking.

The caller's role sets the mandatory classification filter; results carry citations and are
marked as untrusted data.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field

from src.core.errors import ProviderUnavailable
from src.rag.service import KnowledgeService
from src.tools.base import ToolContext, ToolSpec
from src.tools.deps import ToolDeps
from src.tools.inputs import Ticker, ToolInput

DocType = Literal["filing", "statement", "research", "news", "policy", "regulation", "internal"]


class DocSearchInput(ToolInput):
    query: str = Field(min_length=3, max_length=300)
    k: int = Field(default=5, ge=1, le=10)
    doc_types: list[DocType] = Field(default_factory=list, max_length=7)
    ticker: Ticker | None = None
    fiscal_period: str | None = Field(default=None, max_length=12)
    as_of: date | None = None


class ReportSearchInput(ToolInput):
    query: str = Field(min_length=3, max_length=300)
    ticker: Ticker | None = None
    fiscal_period: str | None = Field(default=None, max_length=12)
    k: int = Field(default=5, ge=1, le=10)


class AskInput(ToolInput):
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(default=5, ge=1, le=8)


class RerankInput(ToolInput):
    query: str = Field(min_length=3, max_length=300)
    passages: list[str] = Field(min_length=1, max_length=20)


def build(deps: ToolDeps) -> list[ToolSpec]:
    def service() -> KnowledgeService:
        if deps.kb is None:
            raise ProviderUnavailable("knowledge base not configured")
        return deps.kb

    async def _search(
        args: DocSearchInput, ctx: ToolContext, mode: str, rerank: bool
    ) -> dict[str, Any]:
        kb = service()
        filters = kb.filters(
            ctx.role,
            doc_types=tuple(args.doc_types),
            ticker=args.ticker,
            fiscal_period=args.fiscal_period,
            as_of=args.as_of,
        )
        result = await kb.search(args.query, filters, k=args.k, mode=mode, rerank=rerank)
        out: dict[str, Any] = {"query": args.query} | result.as_dict()
        return out

    async def search_documents(args: DocSearchInput, ctx: ToolContext) -> dict[str, Any]:
        return await _search(args, ctx, "hybrid", True)

    async def hybrid_search(args: DocSearchInput, ctx: ToolContext) -> dict[str, Any]:
        return await _search(args, ctx, "hybrid", False)

    async def vector_search(args: DocSearchInput, ctx: ToolContext) -> dict[str, Any]:
        return await _search(args, ctx, "vector", False)

    async def search_financial_reports(args: ReportSearchInput, ctx: ToolContext) -> dict[str, Any]:
        search = DocSearchInput(
            query=args.query,
            k=args.k,
            doc_types=["filing", "statement"],
            ticker=args.ticker,
            fiscal_period=None,
        )
        result = await _search(search, ctx, "hybrid", True)
        if args.fiscal_period:
            result["results"] = [
                r for r in result["results"] if r["fiscalPeriod"] in (None, args.fiscal_period)
            ]
        return result

    async def rerank_documents(args: RerankInput, ctx: ToolContext) -> dict[str, Any]:
        scores, used = await service().retriever.rerankers.scores(args.query, args.passages)
        order = (
            sorted(range(len(args.passages)), key=lambda i: scores[i], reverse=True)
            if scores
            else list(range(len(args.passages)))
        )
        return {
            "reranker": used,
            "ranking": [
                {"index": i, "score": round(scores[i], 4) if scores else None} for i in order
            ],
        }

    async def answer_from_documents(args: AskInput, ctx: ToolContext) -> dict[str, Any]:
        kb = service()
        return await kb.ask(args.question, kb.filters(ctx.role), k=args.k)

    def spec(name: str, model: type[ToolInput], handler: Any, desc: str) -> ToolSpec:
        return ToolSpec(
            name,
            ("research",),
            desc,
            model,
            handler,
            "agents:run",
            timeout_seconds=30.0,
            source="knowledge_base",
        )

    return [
        spec(
            "search_documents",
            DocSearchInput,
            search_documents,
            "Search the firm's knowledge base (filings, policies, regulations, research): hybrid "
            "vector + BM25, cross-encoder re-ranked, with citations.",
        ),
        spec(
            "answer_from_documents",
            AskInput,
            answer_from_documents,
            "Grounded answer from the knowledge base with [n] citations (validated; refuses when "
            "the documents don't answer).",
        ),
        spec("hybrid_search", DocSearchInput, hybrid_search, "Hybrid search without re-ranking."),
        spec("vector_search", DocSearchInput, vector_search, "Bi-encoder vector search only."),
        spec(
            "search_financial_reports",
            ReportSearchInput,
            search_financial_reports,
            "Search filings and financial statements, optionally for one ticker and period.",
        ),
        spec(
            "rerank_documents",
            RerankInput,
            rerank_documents,
            "Re-rank passages for a query with the cross-encoder.",
        ),
    ]
