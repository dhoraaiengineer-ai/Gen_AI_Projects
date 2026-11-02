"""Grounded, cited manual answers (P1-7, rules/50 + rules/55).

Pipeline: safety pre-checks (bypass / HV DIY → fixed text, no LLM) → hybrid retrieval → evidence threshold
(no evidence → insufficient_evidence, no LLM) → AGENT-chain structured draft → post-validation (citation refs,
verbatim quotes, numbers, forbidden phrases) → safety banner tier + manual's required action.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.errors import LlmUnavailable
from app.rag import safety
from app.rag.retriever import RetrievalFilters, RetrievedChunk, Retriever
from app.services.llm_service import LLM, CallMeta

PROMPT_VERSION = "manual_answer_v1"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_WS = re.compile(r"\s+")


# ── LLM output schema (validated) ──────────────────────────────────────────────────────────────────────
class DraftCitation(BaseModel):
    ref: str = Field(description="Passage ref, e.g. C1")
    quote: str = Field(description="Exact words copied from that passage")


class ManualAnswerDraft(BaseModel):
    answer: str
    citations: list[DraftCitation]
    confidence: float = Field(ge=0, le=1)
    insufficient_evidence: bool


# ── API-facing result ─────────────────────────────────────────────────────────────────────────────────
class Citation(BaseModel):
    chunk_id: str
    source_file: str
    page: int
    section_id: str
    section_title: str
    quote: str


class SafetyInfo(BaseModel):
    safety_critical: bool
    banner_tier: safety.BannerTier
    banner_text: str | None
    required_action_quote: Citation | None = None
    escalation: str | None = None


class ManualAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float
    insufficient_evidence: bool
    safety: SafetyInfo
    refusal_reason: str | None = None  # bypass_request | hv_diy | no_evidence | unsupported_output |
    #                                    service_unavailable


@dataclass(frozen=True)
class AnswerContext:
    role: str
    visibility: str  # owner | staff
    model: str | None
    model_year: int | None
    request_id: str | None = None


# Typographic look-alikes models emit in "verbatim" quotes (non-breaking hyphen, en dash, curly quotes, NBSP).
_TYPO = str.maketrans(
    {chr(c): "-" for c in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014)}
    | {chr(c): "'" for c in (0x2018, 0x2019)}
    | {chr(c): '"' for c in (0x201C, 0x201D)}
    | {chr(c): " " for c in (0x00A0, 0x202F)}
)


def _norm(text: str) -> str:
    return _WS.sub(" ", text.replace("§", "").translate(_TYPO)).strip().casefold()


def _cite(chunk: RetrievedChunk, quote: str) -> Citation:
    md = chunk.metadata
    return Citation(
        chunk_id=str(chunk.chunk_id),
        source_file=str(md.get("source_file")),
        page=int(md.get("page") or 1),
        section_id=str(md.get("section_id")),
        section_title=str(md.get("section_title")),
        quote=" ".join(quote.split()),
    )


UNAVAILABLE = (
    "I can't look this up in the manual right now. Please try again shortly, or contact your Veloxa service centre."
)


def _not_covered(ctx: AnswerContext) -> str:
    model = f"Veloxa {ctx.model}" if ctx.model else "Veloxa"
    return f"I don't have that in the {model} manual excerpts available to me."


def _finish(
    ctx: AnswerContext,
    q: safety.QuestionSafety,
    *,
    answer: str,
    citations: list[Citation],
    cited_chunks: list[RetrievedChunk],
    confidence: float,
    insufficient: bool,
    refusal_reason: str | None = None,
) -> ManualAnswer:
    chunk_safety = any(c.metadata.get("safety_critical") for c in cited_chunks)
    stop_chunks = [c for c in cited_chunks if c.metadata.get("stop_required")]
    topic = q.safety_topic or chunk_safety or bool(stop_chunks)
    tier = safety.banner_tier(
        role=ctx.role, safety_topic=topic, stop_required=bool(stop_chunks), active_symptom=q.active_symptom
    )
    required: Citation | None = None
    for c in stop_chunks or [c for c in cited_chunks if c.metadata.get("safety_critical")]:
        action = safety.required_action(c.content)
        if action:
            required = _cite(c, action)
            break
    return ManualAnswer(
        answer=answer,
        citations=citations,
        confidence=confidence,
        insufficient_evidence=insufficient,
        refusal_reason=refusal_reason,
        safety=SafetyInfo(
            safety_critical=topic,
            banner_tier=tier,
            banner_text=safety.banner_text(tier),
            required_action_quote=required if tier in ("stop", "info", "technician") else None,
            escalation=safety.TEXTS["safety.escalation"] if topic and ctx.visibility == "owner" else None,
        ),
    )


async def answer_question(question: str, ctx: AnswerContext, retriever: Retriever, llm: LLM) -> ManualAnswer:
    q = safety.classify_question(question)

    if q.bypass_request:
        return _finish(
            ctx, q, answer=safety.TEXTS["safety.bypass_refusal"], citations=[], cited_chunks=[],
            confidence=1.0, insufficient=False, refusal_reason="bypass_request",
        )  # fmt: skip

    filters = RetrievalFilters(visibility="owner" if ctx.visibility == "owner" else "staff", model=ctx.model,
                               model_year=ctx.model_year)  # fmt: skip
    try:
        evidence = retriever.evidence(await retriever.search(question, filters))
    except LlmUnavailable:  # degrade, but the deterministic safety banner still applies (NFR-010, rules/55)
        return _finish(ctx, q, answer=UNAVAILABLE, citations=[], cited_chunks=[], confidence=0.0,
                       insufficient=True, refusal_reason="service_unavailable")  # fmt: skip

    if q.hv_diy_request and ctx.visibility == "owner":
        hv = [c for c in evidence if c.metadata.get("safety_critical")][:1]
        cites = [_cite(c, safety.required_action(c.content) or c.content[:200]) for c in hv]
        return _finish(
            ctx, q, answer=safety.TEXTS["safety.ev_hv.owner"], citations=cites, cited_chunks=hv,
            confidence=1.0, insufficient=not hv, refusal_reason="hv_diy",
        )  # fmt: skip

    if not evidence:  # no LLM call without evidence (rules/50)
        return _finish(ctx, q, answer=_not_covered(ctx), citations=[], cited_chunks=[], confidence=0.0,
                       insufficient=True, refusal_reason="no_evidence")  # fmt: skip

    refs = {f"C{i}": c for i, c in enumerate(evidence, start=1)}
    passages = "\n\n".join(
        f"[{ref}] ({c.metadata.get('section_title')}, {c.metadata.get('source_file')} p.{c.metadata.get('page')})\n"
        f"{c.content}"
        for ref, c in refs.items()
    )
    model_line = (
        f"Vehicle: Veloxa {ctx.model} {ctx.model_year or ''}".strip() if ctx.model else "Vehicle: not specified"
    )
    messages = [
        SystemMessage(SYSTEM_PROMPT),
        HumanMessage(
            f"{model_line}\n\n<context>\n{passages}\n</context>\n\n"
            f"<untrusted_user_input>\n{question}\n</untrusted_user_input>"
        ),
    ]
    try:
        draft = await llm.structured(
            ManualAnswerDraft, messages, CallMeta(purpose=PROMPT_VERSION, request_id=ctx.request_id)
        )
    except LlmUnavailable:
        return _finish(ctx, q, answer=UNAVAILABLE, citations=[], cited_chunks=[], confidence=0.0,
                       insufficient=True, refusal_reason="service_unavailable")  # fmt: skip

    # ── post-validation ──
    valid: list[Citation] = []
    cited: list[RetrievedChunk] = []
    for dc in draft.citations:
        chunk = refs.get(dc.ref.strip().upper())
        if chunk is None or not dc.quote.strip() or _norm(dc.quote) not in _norm(chunk.content):
            continue
        valid.append(_cite(chunk, dc.quote))
        if chunk not in cited:
            cited.append(chunk)

    if draft.insufficient_evidence or not valid:
        return _finish(ctx, q, answer=_not_covered(ctx), citations=[], cited_chunks=[], confidence=0.0,
                       insufficient=True, refusal_reason="no_evidence")  # fmt: skip

    # Numbers may come only from cited text or from the vehicle header we supplied (e.g. the model year).
    cited_text = " ".join([_norm(model_line), *(_norm(c.content) for c in cited)])
    unsupported = [n for n in _NUMBER.findall(draft.answer) if n.casefold() not in cited_text]
    if unsupported or safety.forbidden_phrases_in(draft.answer):
        return _finish(ctx, q, answer=_not_covered(ctx), citations=valid, cited_chunks=cited, confidence=0.0,
                       insufficient=True, refusal_reason="unsupported_output")  # fmt: skip

    return _finish(ctx, q, answer=draft.answer.strip(), citations=valid, cited_chunks=cited,
                   confidence=draft.confidence, insufficient=False)  # fmt: skip
