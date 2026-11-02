"""Diagnosis node (specs/agents/04-diagnosis.md). AGENT chain, grounded in staff-visibility chunks.

Pipeline: DTC format check (deterministic) → bypass/disable refusal (no LLM) → DTC meanings by EXACT section lookup
→ TSB match (model + year + VIN range AND DTC/keyword) → evidence = DTC chunks + service-manual sections they reference
+ matched TSB chunks + hybrid retrieval → AGENT-chain ranked hypotheses → post-validation (≥ 1 verbatim citation,
no rewritten spec values, no unsupported numbers, no forbidden phrases, ≤ 5) → technician safety banner (rules/55).
The technician decides; this is a preliminary assessment (safety.ai_panel).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidDtc, LlmUnavailable
from app.graph.deps import NodeDeps, run_node
from app.graph.loaders import latest_finding
from app.graph.nodes.vehicle_context import match_tsbs
from app.graph.state import ServiceGraphState
from app.models import KnowledgeChunk
from app.rag import safety
from app.rag.answer import Citation, SafetyInfo, _cite, _norm
from app.rag.retriever import RetrievalFilters, RetrievedChunk, Retriever
from app.rules.recall_match import VehicleKey
from app.schemas.diagnosis import DiagnosisIn, DiagnosisResult, DtcMeaningOut, HypothesisOut
from app.schemas.graph import DiagnosisSummary
from app.schemas.vehicle_context import TsbMatchOut
from app.services.llm_service import LLM, CallMeta

log = structlog.get_logger(__name__)

PROMPT_VERSION = "diagnosis_v1"
SYSTEM_PROMPT = (Path(__file__).resolve().parents[2] / "rag" / "prompts" / f"{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)
DTC_FORMAT = re.compile(r"^[PBCU][0-9A-F]{4}$")
MAX_HYPOTHESES = 5
MAX_EVIDENCE = 10
_SECTION_REF = re.compile(r"service manual section (\d+\.\d+)", re.IGNORECASE)
# Clearing stored codes is routine workshop practice, not a bypass request ("cleared codes, EGR still lags").
_ROUTINE_CLEAR = re.compile(
    r"\b(clear(ed|ing)?|reset)\s+(the\s+|all\s+)?(dtcs?|codes?|fault codes?|faults?)\b", re.IGNORECASE
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Passage refs the model sometimes writes into prose ("matches C1:", "(C2)"). Not DTCs: C0035 has 4 digits.
_PASSAGE_REF = re.compile(r"\s*\(?\b[Cc]\d{1,2}\b\)?:?")
# A number with a unit is a specification value: it may appear only inside a quote (rules/50).
_SPEC_VALUE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:n·m|nm|n m|mm|ohms?|Ω|mv|kpa|bar|psi|ml|°c|g|v|l|a)(?![\w·])", re.IGNORECASE
)


# ── LLM output schema ──────────────────────────────────────────────────────────────────────────────────
class DraftQuote(BaseModel):
    ref: str = Field(description="Passage ref, e.g. C1")
    quote: str = Field(description="Exact words copied from that passage")


class DraftHypothesis(BaseModel):
    cause: str
    evidence: str
    citations: list[DraftQuote]
    confidence: float = Field(ge=0, le=1)
    next_test: DraftQuote | None = None


class DiagnosisDraft(BaseModel):
    hypotheses: list[DraftHypothesis]
    insufficient_evidence: bool

    @model_validator(mode="after")
    def _consistent(self) -> DiagnosisDraft:
        # "No hypotheses, yet evidence is sufficient" is a malformed reply (seen from some models) → the LLM service
        # treats it as invalid structured output and falls back to the next model in the chain.
        if not self.hypotheses and not self.insufficient_evidence:
            raise ValueError("no hypotheses but insufficient_evidence is false")
        return self


@dataclass(frozen=True)
class DiagnosisContext:
    model: str | None
    model_id: uuid.UUID | None
    model_year: int | None
    vin: str | None
    complaint: str = ""
    role: str = "technician"
    request_id: str | None = None


def validate_dtcs(codes: list[str]) -> list[str]:
    """Upper-case, de-duplicate (order kept), and reject anything not P/B/C/U + 4 hex characters."""
    cleaned = [c.strip().upper() for c in codes if c.strip()]
    invalid = [c for c in cleaned if not DTC_FORMAT.match(c)]
    if invalid:
        raise InvalidDtc(f"Invalid DTC format: {', '.join(invalid)}. Expected e.g. P0301.", {"invalid": invalid})
    return list(dict.fromkeys(cleaned))


def _technician_text(inp: DiagnosisIn) -> str:
    tests = "; ".join(f"{t.name}: {t.value}{' ' + t.unit if t.unit else ''}" for t in inp.test_results)
    return "\n".join(p for p in (inp.symptoms, inp.freeze_frame_notes or "", tests) if p.strip())


def _as_retrieved(row: KnowledgeChunk) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=row.id, content=row.content, metadata=dict(row.chunk_metadata), exact_match=True)


async def _chunk_by_section(session: AsyncSession, section_id: str) -> RetrievedChunk | None:
    row = await session.scalar(
        select(KnowledgeChunk).where(KnowledgeChunk.chunk_metadata["section_id"].astext == section_id).limit(1)
    )
    return _as_retrieved(row) if row is not None else None


async def lookup_dtc(session: AsyncSession, code: str) -> RetrievedChunk | None:
    """Exact-match only: the DTC reference section whose id is the code. Never a fuzzy or LLM guess."""
    chunk = await _chunk_by_section(session, f"dtc_reference#{code}")
    return chunk if chunk is not None and chunk.metadata.get("doc_type") == "dtc" else None


def _meaning_line(chunk: RetrievedChunk) -> str:
    return " ".join(chunk.content.split("\n", 1)[0].replace("§", "").split())


def _certified_sentence(chunks: list[RetrievedChunk]) -> Citation | None:
    for c in chunks:
        for sentence in re.findall(r"[^.\n]*[Cc]ertified[^.\n]*\.", c.content):
            return _cite(c, sentence.strip())
    return None


def _result(
    *,
    meanings: list[DtcMeaningOut],
    hypotheses: list[HypothesisOut],
    tsbs: list[TsbMatchOut],
    safety_chunks: list[RetrievedChunk],
    safety_text: str,
    insufficient: bool,
    refusal_reason: str | None = None,
    dropped: int = 0,
) -> DiagnosisResult:
    q = safety.classify_question(safety_text)
    flagged = [c for c in safety_chunks if c.metadata.get("safety_critical")]
    topic = q.safety_topic or bool(flagged)
    tier = safety.banner_tier(role="technician", safety_topic=topic, stop_required=False, active_symptom=False)
    return DiagnosisResult(
        dtc_meanings=meanings,
        hypotheses=hypotheses,
        matched_tsbs=tsbs,
        insufficient_evidence=insufficient,
        refusal_reason=refusal_reason,
        dropped_hypotheses=dropped,
        ai_label=safety.TEXTS["safety.ai_panel"],
        safety=SafetyInfo(
            safety_critical=topic,
            banner_tier=tier,
            banner_text=safety.banner_text(tier),
            required_action_quote=_certified_sentence(flagged + safety_chunks) if topic else None,
        ),
    )


async def diagnose(
    session: AsyncSession, inp: DiagnosisIn, ctx: DiagnosisContext, retriever: Retriever, llm: LLM
) -> DiagnosisResult:
    dtcs = validate_dtcs(inp.dtcs)
    tech_text = _technician_text(inp)

    if safety.classify_question(_ROUTINE_CLEAR.sub(" ", tech_text)).bypass_request:
        log.warning("safety_refusal", reason="bypass_request", node="diagnosis", metric="safety_refusals_total")
        return _result(
            meanings=[], hypotheses=[], tsbs=[], safety_chunks=[], safety_text=tech_text,
            insufficient=False, refusal_reason="bypass_request",
        )  # fmt: skip

    # 1) DTC meanings — exact section lookup
    meanings: list[DtcMeaningOut] = []
    dtc_chunks: list[RetrievedChunk] = []
    for code in dtcs:
        chunk = await lookup_dtc(session, code)
        if chunk is None:
            meanings.append(DtcMeaningOut(code=code, not_found=True))
            continue
        meanings.append(DtcMeaningOut(code=code, meaning_quote=_cite(chunk, _meaning_line(chunk))))
        dtc_chunks.append(chunk)

    # 2) TSBs — deterministic (ADR-006)
    tsbs: list[TsbMatchOut] = []
    if ctx.model_id and ctx.model_year and ctx.vin:
        key = VehicleKey(model_id=ctx.model_id, model_year=ctx.model_year, vin=ctx.vin)
        tsbs = await match_tsbs(session, key, dtcs, f"{tech_text}\n{ctx.complaint}")

    # 3) Evidence: deterministic chunks first, then hybrid retrieval (staff visibility)
    evidence: dict[uuid.UUID, RetrievedChunk] = {c.chunk_id: c for c in dtc_chunks}
    if ctx.model:
        for chunk in dtc_chunks:
            for number in _SECTION_REF.findall(chunk.content):
                ref = await _chunk_by_section(session, f"service_manual_{ctx.model.lower()}#{number}")
                if ref is not None:
                    evidence.setdefault(ref.chunk_id, ref)
    for tsb in tsbs:
        if tsb.source:
            ref = await _chunk_by_section(session, tsb.source.section_id)
            if ref is not None:
                evidence.setdefault(ref.chunk_id, ref)
    query = " ".join([*dtcs, *(_meaning_line(c) for c in dtc_chunks), inp.symptoms, inp.freeze_frame_notes or "",
                      ctx.complaint])  # fmt: skip
    filters = RetrievalFilters(
        visibility="staff", model=ctx.model, model_year=ctx.model_year, doc_types=("service_manual", "tsb", "dtc")
    )
    try:
        for chunk in retriever.evidence(await retriever.search(query, filters)):
            evidence.setdefault(chunk.chunk_id, chunk)
    except LlmUnavailable:  # embeddings down: deterministic evidence (DTC refs, TSBs) still supports a diagnosis
        log.warning("diagnosis_retrieval_degraded", reason="embeddings_unavailable")
    chunks = list(evidence.values())[:MAX_EVIDENCE]
    safety_text = "\n".join([tech_text, ctx.complaint, *(_meaning_line(c) for c in dtc_chunks)])

    if not chunks:  # no LLM call without evidence (rules/50)
        return _result(meanings=meanings, hypotheses=[], tsbs=tsbs, safety_chunks=[], safety_text=safety_text,
                       insufficient=True, refusal_reason="no_evidence")  # fmt: skip

    refs = {f"C{i}": c for i, c in enumerate(chunks, start=1)}
    passages = "\n\n".join(
        f"[{ref}] ({c.metadata.get('doc_type')}: {c.metadata.get('section_title')}, {c.metadata.get('source_file')})\n"
        f"{c.content}"
        for ref, c in refs.items()
    )
    header = f"Vehicle: Veloxa {ctx.model} {ctx.model_year or ''}".strip() if ctx.model else "Vehicle: not specified"
    inputs = (
        f"DTCs: {', '.join(dtcs) or 'none'}\nSymptoms: {inp.symptoms or 'none'}\n"
        f"Freeze-frame notes: {inp.freeze_frame_notes or 'none'}\n"
        f"Test results: {'; '.join(f'{t.name}={t.value}{t.unit or ""}' for t in inp.test_results) or 'none'}\n"
        f"Customer complaint: {ctx.complaint or 'none'}"
    )
    messages = [
        SystemMessage(SYSTEM_PROMPT),
        HumanMessage(
            f"{header}\n\n<context>\n{passages}\n</context>\n\n<untrusted_user_input>\n{inputs}\n</untrusted_user_input>"
        ),
    ]
    try:
        draft = await llm.structured(
            DiagnosisDraft, messages, CallMeta(purpose=PROMPT_VERSION, request_id=ctx.request_id)
        )
    except LlmUnavailable:  # spec: return DTC meanings + matched TSBs only
        return _result(meanings=meanings, hypotheses=[], tsbs=tsbs, safety_chunks=dtc_chunks,
                       safety_text=safety_text, insufficient=True, refusal_reason="service_unavailable")  # fmt: skip

    # ── post-validation ──
    allowed_numbers = " ".join([_norm(header), _norm(tech_text), _norm(" ".join(dtcs))])
    kept: list[tuple[DraftHypothesis, list[Citation], list[RetrievedChunk], Citation | None]] = []
    dropped = 0
    for h in draft.hypotheses:
        cites: list[Citation] = []
        cited: list[RetrievedChunk] = []
        for dq in h.citations:
            chunk = refs.get(dq.ref.strip().upper())
            if chunk is None or not dq.quote.strip() or _norm(dq.quote) not in _norm(chunk.content):
                continue
            cites.append(_cite(chunk, dq.quote))
            if chunk not in cited:
                cited.append(chunk)
        h.cause, h.evidence = _PASSAGE_REF.sub("", h.cause).strip(), _PASSAGE_REF.sub("", h.evidence).strip()
        prose = f"{h.cause} {h.evidence}"
        supported = " ".join([allowed_numbers, *(_norm(c.content) for c in cited)])
        rewritten_spec = [s for s in _SPEC_VALUE.findall(prose) if _norm(s) not in _norm(tech_text)]
        unsupported = [n for n in _NUMBER.findall(prose) if n.casefold() not in supported]
        forbidden = safety.forbidden_phrases_in(prose)
        if not cites or rewritten_spec or unsupported or forbidden or not h.cause.strip():
            dropped += 1
            reasons = [
                r
                for r, bad in (
                    ("uncited", not cites),
                    ("spec_value", rewritten_spec),
                    ("unsupported_number", unsupported),
                    ("forbidden_phrase", forbidden),
                )
                if bad
            ]
            log.info(
                "diagnosis_hypothesis_dropped",
                reasons=reasons,
                numbers=unsupported,
                specs=rewritten_spec,
                n_quotes=len(h.citations),
            )
            continue
        next_test: Citation | None = None
        if h.next_test is not None:
            chunk = refs.get(h.next_test.ref.strip().upper())
            if (
                chunk is not None
                and chunk.metadata.get("doc_type") in ("service_manual", "tsb")
                and h.next_test.quote.strip()
                and _norm(h.next_test.quote) in _norm(chunk.content)
            ):
                next_test = _cite(chunk, h.next_test.quote)
        kept.append((h, cites, cited, next_test))

    kept.sort(key=lambda k: -k[0].confidence)
    dropped += max(0, len(kept) - MAX_HYPOTHESES)
    kept = kept[:MAX_HYPOTHESES]
    hypotheses = [
        HypothesisOut(
            rank=i,
            cause=h.cause.strip(),
            evidence=h.evidence.strip(),
            citations=cites,
            confidence=round(h.confidence, 2),
            next_test=nt,
        )
        for i, (h, cites, _, nt) in enumerate(kept, start=1)
    ]
    cited_chunks = list({c.chunk_id: c for _, _, cs, _ in kept for c in cs}.values())
    return _result(
        meanings=meanings, hypotheses=hypotheses, tsbs=tsbs, safety_chunks=dtc_chunks + cited_chunks,
        safety_text=safety_text, insufficient=not hypotheses,
        refusal_reason=None if hypotheses else "no_evidence", dropped=dropped,
    )  # fmt: skip


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    """Graph node 4 (workflow): the technician-CONFIRMED finding drives warranty/estimate — never the AI hypotheses.

    The copilot (`diagnose`) is called from the technician API; here we read diagnostic_findings. Safety flag: any
    confirmed DTC whose reference entry names a safety system raises `safety_critical` (OR-reducer).
    """

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        f = await latest_finding(s, uuid.UUID(state["ro_id"]))
        if f is None:
            return {
                "diagnosis": DiagnosisSummary(finding_id=None, confirmed_hypothesis=None).model_dump(mode="json")
            }, "ok"
        summary = DiagnosisSummary(
            finding_id=str(f.id),
            confirmed_hypothesis=f.confirmed_hypothesis,
            dtcs=list(f.dtcs or []),
            op_codes=list(f.op_codes_performed or []),
            parts=[{"part_number": str(p["part_number"]), "qty": str(p["qty"])} for p in (f.parts_used or [])],
            actual_hours=str(f.actual_hours) if f.actual_hours is not None else None,
        )
        meanings = [_meaning_line(c) for code in summary.dtcs if (c := await lookup_dtc(s, code)) is not None]
        q = safety.classify_question("\n".join([*meanings, summary.confirmed_hypothesis or ""]))
        return {"diagnosis": summary.model_dump(mode="json"), "safety_critical": q.safety_topic}, "ok"

    # Pure read of the latest finding: never cached, nothing to audit.
    return await run_node(deps, state, "diagnosis", {"ro_id": state["ro_id"]}, body, cache=False, audit=False)
