"""Use cases the API exposes. Routes call this; this calls the graphs, retriever and golden store."""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from prometheus_client import Counter

from app.agents.research_agent import WEB_TOOL_NAME
from app.core.metrics import AGENT_TOOL_CALLS, CHUNKS_INGESTED, DOCUMENTS_RETRIEVED
from app.models.schemas import (
    AgentResponse,
    DeleteDocumentResponse,
    DocumentIn,
    DocumentInfo,
    DocumentListResponse,
    DocumentResult,
    EvalItemOut,
    EvalResponse,
    GoldenItemIn,
    GoldenItemOut,
    IngestResponse,
    QueryResponse,
    SourceChunk,
)
from app.rag.cache import AnswerCache
from app.rag.chunking import ChunkingStrategy
from app.rag.evaluation import Evaluator
from app.rag.golden import GoldenGenerator, GoldenItem, GoldenStore
from app.rag.grounding import check_grounding
from app.rag.loaders import Section, UnsupportedFileError, load_file
from app.rag.memory import ChatTurn, ConversationMemory, SessionSummary, format_history
from app.rag.prompts import CONDENSE_SYSTEM_PROMPT, CONDENSE_USER_TEMPLATE
from app.rag.ragas_metrics import METRICS
from app.rag.retriever import IngestResult, IngestStatus, Retriever

logger = logging.getLogger(__name__)
audit = logging.getLogger("app.audit")

_CITATION = re.compile(r"\[\d+\]")
HALLUCINATION_FLAGS = Counter("rag_hallucination_flags_total", "Answers that failed the grounding check", ["mode"])
BLOCKED_ANSWER = "I couldn't find a well-supported answer in the documents. Try rephrasing, or check the sources below."


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    data: bytes


class RAGService:
    def __init__(
        self,
        retriever: Retriever,
        rag_graph: CompiledStateGraph,
        research_agent: CompiledStateGraph,
        model_name: str,
        agent_max_iterations: int,
        golden_store: GoldenStore,
        golden_generator: GoldenGenerator,
        evaluator: Evaluator,
        answer_cache: AnswerCache | None = None,
        memory: ConversationMemory | None = None,
        rewriter: Runnable[LanguageModelInput, BaseMessage] | None = None,
        audit_content: bool = True,
        hallucination_guard: str = "flag",
    ):
        self.retriever = retriever
        self.rag_graph = rag_graph
        self.research_agent = research_agent
        self.model_name = model_name
        self.agent_max_iterations = agent_max_iterations
        self.golden_store = golden_store
        self.golden_generator = golden_generator
        self.evaluator = evaluator
        self.answer_cache = answer_cache
        self.memory = memory
        self.rewriter = rewriter  # turns a follow-up into a standalone question
        self.audit_content = audit_content
        self.hallucination_guard = hallucination_guard

    # ---------- Ingest ----------

    def ingest(
        self,
        documents: list[DocumentIn],
        strategy: ChunkingStrategy | None = None,
        overlap_pct: float | None = None,
    ) -> IngestResponse:
        strategy = strategy or self.retriever.default_strategy
        results = [self._ingest_one(d.source, [Section(d.text)], d.metadata, strategy, overlap_pct) for d in documents]
        return self._response(results, strategy)

    def ingest_files(
        self,
        files: Sequence[UploadedFile],
        strategy: ChunkingStrategy | None = None,
        overlap_pct: float | None = None,
    ) -> IngestResponse:
        """Parse each file (PDF, Excel, Word, PowerPoint, CSV, text) and ingest it. One bad file doesn't fail
        the others: it's reported with status "failed". Spreadsheets default to the table strategy."""
        results: list[DocumentResult] = []
        for upload in files:
            try:
                loaded = load_file(upload.filename, upload.data)
            except UnsupportedFileError as exc:
                results.append(DocumentResult(source=upload.filename, status="failed", error=str(exc)))
                continue
            chosen = strategy or (ChunkingStrategy.TABLE if loaded.tabular else self.retriever.default_strategy)
            results.append(self._ingest_one(upload.filename, loaded.sections, {}, chosen, overlap_pct))
        return self._response(results, strategy or self.retriever.default_strategy)

    def _ingest_one(
        self,
        source: str,
        sections: list[Section],
        metadata: dict[str, str],
        strategy: ChunkingStrategy,
        overlap_pct: float | None,
    ) -> DocumentResult:
        result = self.retriever.ingest(source, sections, metadata, strategy, overlap_pct)
        CHUNKS_INGESTED.inc(result.added)
        golden = self._refresh_golden(result) if result.status in (IngestStatus.ADDED, IngestStatus.UPDATED) else 0
        return DocumentResult(
            source=source,
            status=result.status.value,
            chunking=result.chunking,
            chunks=result.chunks,
            added=result.added,
            removed=result.removed,
            golden_questions=golden,
        )

    def _refresh_golden(self, result: IngestResult) -> int:
        """New or changed content gets fresh generated Q&A. A failure here never fails the upload."""
        try:
            items = self.golden_generator.generate(result.source, result.documents)
            self.golden_store.replace_generated(result.source, items)
            return len(items)
        except Exception:
            logger.warning("golden Q&A generation failed", extra={"source": result.source}, exc_info=True)
            return 0

    def _response(self, results: list[DocumentResult], strategy: ChunkingStrategy) -> IngestResponse:
        if self.answer_cache and any(r.status in ("added", "updated", "empty") for r in results):
            self.answer_cache.invalidate()  # cached answers may now be stale
        audit.info(
            "documents ingested",
            extra={"documents": [f"{r.source}:{r.status}" for r in results], "chunking": strategy.value},
        )
        return IngestResponse(
            documents=len(results), chunks=sum(r.added for r in results), chunking=strategy, results=results
        )

    # ---------- Documents ----------

    def list_documents(self) -> DocumentListResponse:
        docs = [
            DocumentInfo(source=r.source, chunking=r.chunking, chunks=len(r.chunk_ids))
            for r in self.retriever.documents()
        ]
        return DocumentListResponse(count=len(docs), documents=docs)

    def delete_document(self, source: str) -> DeleteDocumentResponse | None:
        """Delete a document's chunks, registry record and golden Q&A. None if the source isn't indexed."""
        if self.retriever.registry.get(source) is None:
            return None
        chunks = self.retriever.delete(source)
        golden = self.golden_store.delete_source(source)
        if self.answer_cache:
            self.answer_cache.invalidate()
        audit.info("document deleted", extra={"source": source, "chunks": chunks, "golden": golden})
        return DeleteDocumentResponse(source=source, chunks_deleted=chunks, golden_deleted=golden)

    # ---------- Golden dataset + evaluation ----------

    def list_golden(self, source: str | None = None, limit: int | None = None) -> list[GoldenItemOut]:
        return [_golden_out(item) for item in self.golden_store.list(source, limit)]

    def import_golden(self, items: list[GoldenItemIn]) -> int:
        golden = [GoldenItem.create(i.source, i.question, i.answer, i.evidence, i.location, "manual") for i in items]
        self.golden_store.upsert(golden)
        return len(golden)

    def evaluate(
        self,
        source: str | None,
        limit: int,
        top_k: int | None,
        judge: bool,
        metrics: Sequence[str] = METRICS,
    ) -> EvalResponse:
        report = self.evaluator.run(self.golden_store.list(source, limit), top_k, judge, metrics)
        return EvalResponse(
            count=len(report.items),
            top_k=report.top_k,
            judged=report.judged,
            evidence_hit_rate=report.evidence_hit_rate,
            source_hit_rate=report.source_hit_rate,
            mrr=report.mrr,
            answer_accuracy=report.answer_accuracy,
            citation_accuracy=report.citation_accuracy,
            grounded_rate=report.grounded_rate,
            **{m: report.ragas_mean(m) for m in METRICS},
            items=[
                EvalItemOut(
                    question=r.item.question,
                    expected_answer=r.item.answer,
                    source=r.item.source,
                    evidence=r.item.evidence,
                    retrieved=r.retrieved,
                    evidence_rank=r.evidence_rank,
                    source_hit=r.source_hit,
                    answer=r.answer,
                    correct=r.correct,
                    judge_reason=r.judge_reason,
                    cited_expected_source=r.cited_expected_source,
                    grounded=r.grounded,
                    **{m: r.ragas.get(m) for m in METRICS},
                )
                for r in report.items
            ],
        )

    # ---------- Ask ----------

    def query(
        self,
        question: str,
        top_k: int | None = None,
        user_id: str = "anonymous",
        session_id: str | None = None,
    ) -> QueryResponse:
        history = self.memory.recent(user_id, session_id) if self.memory and session_id else []
        standalone = self._standalone_question(question, history)

        cached = self.answer_cache.get(standalone, top_k) if self.answer_cache else None
        if cached is not None:
            response = QueryResponse(**{**cached, "cached": True})
        else:
            # A rewritten follow-up can drift from the user's own words; search with both.
            extra = [question] if standalone != question else []
            state = self.rag_graph.invoke({"question": standalone, "search_queries": extra, "top_k": top_k})
            chunks = state.get("chunks", [])
            DOCUMENTS_RETRIEVED.observe(len(chunks))
            sources = [
                SourceChunk(source=c.source, location=c.location, text=c.document.page_content, score=round(c.score, 4))
                for c in chunks
            ]
            response = QueryResponse(
                answer=state["answer"], sources=sources, model=state.get("model") or self.model_name
            )
            self._apply_grounding(response, chunks)
            # Only cache grounded, cited answers: "the documents don't say" may be a retrieval miss, and
            # caching it (or an ungrounded answer) would repeat it for every user for the whole TTL.
            if self.answer_cache and chunks and response.grounded is not False and _CITATION.search(response.answer):
                self.answer_cache.set(standalone, top_k, response.model_dump(exclude={"cached", "standalone_question"}))
        if standalone != question:
            response.standalone_question = standalone

        if self.memory and session_id:
            self.memory.remember(user_id, session_id, question, response.answer)
        self._audit(
            "question answered",
            user_id,
            session_id,
            question=question,
            answer=response.answer,
            model=response.model,
            cached=response.cached,
            sources=[f"{s.source}{', ' + s.location if s.location else ''}" for s in response.sources],
        )
        return response

    def run_agent(self, task: str, user_id: str = "anonymous", session_id: str | None = None) -> AgentResponse:
        history = self.memory.recent(user_id, session_id) if self.memory and session_id else []
        messages: list[BaseMessage] = [
            HumanMessage(t.content) if t.role == "user" else AIMessage(t.content) for t in history
        ]
        # Each iteration is an agent step plus a tools step.
        config = {"recursion_limit": 2 * self.agent_max_iterations + 1}
        try:
            state = self.research_agent.invoke({"messages": [*messages, HumanMessage(task)]}, config=config)
        except GraphRecursionError:
            logger.warning("agent hit iteration limit", extra={"limit": self.agent_max_iterations})
            return AgentResponse(
                answer="The agent hit its search limit before finishing. Try a narrower question.",
                tool_calls=self.agent_max_iterations,
                model=self.model_name,
            )

        messages = state["messages"]
        tool_calls = sum(len(m.tool_calls) for m in messages if isinstance(m, AIMessage))
        web_sources = list(
            dict.fromkeys(  # dedupe, keep the order the agent saw them
                url
                for m in messages
                if isinstance(m, ToolMessage) and m.name == WEB_TOOL_NAME and isinstance(m.artifact, list)
                for url in m.artifact
            )
        )
        AGENT_TOOL_CALLS.observe(tool_calls)
        final = messages[-1]
        answer = str(final.content).strip() if isinstance(final, AIMessage) else ""
        answered_by = final.response_metadata.get("model_name") if isinstance(final, AIMessage) else None
        response = AgentResponse(
            answer=answer or "The agent stopped without producing an answer.",
            tool_calls=tool_calls,
            model=answered_by or self.model_name,
            web_sources=web_sources,
        )
        if self.memory and session_id:
            self.memory.remember(user_id, session_id, task, response.answer)
        self._audit(
            "research answered",
            user_id,
            session_id,
            question=task,
            answer=response.answer,
            model=response.model,
            tool_calls=tool_calls,
            web_sources=web_sources,
        )
        return response

    # ---------- Conversations ----------

    def conversation(self, user_id: str, session_id: str) -> list[ChatTurn]:
        return self.memory.history(user_id, session_id) if self.memory else []

    def sessions(self, user_id: str) -> list[SessionSummary]:
        return self.memory.sessions(user_id) if self.memory else []

    def _apply_grounding(self, response: QueryResponse, chunks: list) -> None:
        """Hallucination guard: flag (or, in block mode, replace) answers not supported by the passages."""
        if self.hallucination_guard == "off" or not chunks:
            return
        report = check_grounding(response.answer, chunks)
        response.grounded = report.grounded
        response.grounding_issues = report.issues
        if not report.grounded:
            HALLUCINATION_FLAGS.labels(self.hallucination_guard).inc()
            logger.warning("answer failed grounding check", extra={"issues": report.issues})
            if self.hallucination_guard == "block":
                response.answer = BLOCKED_ANSWER

    def _standalone_question(self, question: str, history: list[ChatTurn]) -> str:
        """A follow-up ("what about its ISSN?") is rewritten using the conversation; a failure keeps the original."""
        if not history or self.rewriter is None:
            return question
        prompt = CONDENSE_USER_TEMPLATE.format(history=format_history(history), question=question)
        try:
            rewritten = str(self.rewriter.invoke([SystemMessage(CONDENSE_SYSTEM_PROMPT), HumanMessage(prompt)]).content)
        except Exception:
            logger.warning("follow-up rewrite failed; using the question as asked", exc_info=True)
            return question
        return rewritten.strip().strip('"') or question

    def _audit(self, event: str, user_id: str, session_id: str | None, **details: object) -> None:
        """One log line per user action. Question/answer text is included unless AUDIT_LOG_CONTENT=false."""
        if not self.audit_content:
            details = {k: v for k, v in details.items() if k not in ("question", "answer")}
        else:
            details = {k: (v[:500] if isinstance(v, str) else v) for k, v in details.items()}
        audit.info(event, extra={"user_id": user_id, "session_id": session_id, **details})


def _golden_out(item: GoldenItem) -> GoldenItemOut:
    return GoldenItemOut(
        id=item.id,
        source=item.source,
        question=item.question,
        answer=item.answer,
        evidence=item.evidence,
        location=item.location,
        origin=item.origin,
    )
