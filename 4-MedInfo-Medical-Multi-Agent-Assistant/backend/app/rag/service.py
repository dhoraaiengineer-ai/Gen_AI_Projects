"""Chat use case. Every answer path runs: input guardrails (local PHI redaction) -> triage -> scope ->
[answer cache] -> retrieve/generate -> post-answer checks -> output guardrails -> fixed safety wording.
None of these steps can be switched off by request parameters."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any

from app.core.audit import AuditLogger
from app.core.errors import InputRejectedError
from app.core.logging import request_id_var
from app.core.metrics import CHAT_LATENCY, REFUSALS, SAFETY_CHECK_FAILURES
from app.guardrails.engine import GuardResult, PolicyEngine
from app.rag.cache import AnswerCache
from app.rag.interfaces import Passage, SearchFilter
from app.rag.memory import ConversationNotFoundError, MemoryService
from app.rag.prompts import AnswerMode, split_limitations
from app.rag.review import ReviewService
from app.rag.schemas import ChatAnswer, Citation, EmergencyNotice, SafetyInfo
from app.rag.trace import AgentTrace
from app.rag.versions import apply_version_preference
from app.safety import templates as T
from app.safety.answer_checks import (
    MED_CONTEXT_RE,
    AnswerChecker,
    CheckName,
    check_dosing,
    check_drug_names,
    check_numbers,
    citations_in,
    is_diagnostic_sentence,
    is_high_risk,
    stale_passages,
)
from app.safety.scope import Scope, ScopeClassifier
from app.safety.text import split_sentences
from app.safety.triage import TriageResult, TriageService

logger = logging.getLogger(__name__)

_RESULT_STATUS = {
    "answer": "ok",
    "not_covered": "warn",
    "redirect": "warn",
    "refusal": "stop",
    "emergency": "stop",
}

_MODE_FOR_SCOPE = {
    Scope.INFO: AnswerMode.STANDARD,
    Scope.RESEARCH: AnswerMode.STANDARD,
    Scope.EMERGENCY: AnswerMode.STANDARD,
    Scope.PERSONAL_DIAGNOSIS: AnswerMode.EDUCATIONAL,
    Scope.PRESCRIBING_OR_DOSING: AnswerMode.QUOTE_ONLY,
}


class ChatService:
    def __init__(
        self,
        *,
        triage: TriageService,
        scope: ScopeClassifier,
        rag_graph: Any,
        checker: AnswerChecker,
        contacts: T.SafetyContacts,
        lexicon: frozenset[str],
        audit: AuditLogger,
        top_k: int,
        stale_years: int,
        max_question_chars: int,
        guard: PolicyEngine | None = None,
        cache: AnswerCache | None = None,
        memory: MemoryService | None = None,
        research_graph: Any = None,
        review: ReviewService | None = None,
        today: date | None = None,
    ) -> None:
        self._triage = triage
        self._scope = scope
        self._graph = rag_graph
        self._checker = checker
        self._contacts = contacts
        self._lexicon = lexicon
        self._audit = audit
        self._top_k = top_k
        self._stale_years = stale_years
        self._max_chars = max_question_chars
        self._today = today
        self._guard = guard
        self._cache = cache
        self._memory = memory
        self._research_graph = research_graph
        self._review = review

    # ---- public -------------------------------------------------------------------------------
    def answer(
        self,
        question: str,
        *,
        user_id: str,
        filters: SearchFilter | None = None,
        history: list[tuple[str, str]] | None = None,
        conversation_id: str | None = None,
        research: bool = False,
        capture: list[Passage] | None = None,
        on_phase: Callable[[str], None] | None = None,
    ) -> ChatAnswer:
        """`capture` (evaluation only): receives the passages the answer was generated from.
        `on_phase`: called with real pipeline phases (safety, searching, generating, verifying)."""
        started = time.perf_counter()
        q = question.strip()
        if not q:
            raise InputRejectedError("Please enter a question.")
        if len(q) > self._max_chars:
            fallback = self.rules_emergency_answer(q)  # a long emergency description still gets the notice
            if fallback is not None:
                return fallback
            raise InputRejectedError(f"Questions are limited to {self._max_chars} characters.")

        phase = on_phase or (lambda _name: None)
        phase("safety")
        trace = AgentTrace()
        # Input guardrails are local: PHI is redacted before ANY model call, cache key or storage.
        g_in = self._guard.check_input(q) if self._guard else GuardResult(text=q)
        rules = sorted({e.rule for e in g_in.events})
        if g_in.blocked:
            trace.step("Input guardrails", "blocked", ", ".join(rules), "stop")
        elif g_in.events:
            trace.step("Input guardrails", "redacted / flagged", ", ".join(rules), "warn")
        else:
            trace.step("Input guardrails", "passed", "no personal data or injection patterns found")
        conv = None
        hist = list(history or [])
        if self._memory is not None:
            try:
                # Blocked input (e.g. injection) never becomes a stored title either.
                title = "Message not processed" if g_in.blocked else g_in.text
                conv = self._memory.start_or_get(conversation_id, user_id, title)
                if conversation_id:
                    hist = self._memory.history(conv)
            except ConversationNotFoundError:
                # A stale/unknown conversation must never hide an emergency notice.
                fallback = self.rules_emergency_answer(q)
                if fallback is not None:
                    return fallback
                raise
            except Exception as exc:  # memory outage: answer without history rather than fail
                logger.warning(
                    "conversation memory unavailable; answering without it",
                    extra={"error": type(exc).__name__},
                )
                conv, hist = None, []

        result: ChatAnswer | None = None
        try:
            # A user can only ever search the trusted corpus plus their OWN uploads.
            f = replace(filters or SearchFilter(), owner_id=user_id)
            result = self._answer(q, g_in, f, hist, user_id, research, capture, phase, trace)
            trace.step(
                "Result",
                result.kind.replace("_", " "),
                f"scope: {result.scope}",
                _RESULT_STATUS.get(result.kind, "ok"),
            )
            result.safety = result.safety.model_copy(update={"trace": trace.steps})
            if self._review is not None and not result.cached:
                self._review.maybe_sample(g_in.text, result)
            if conv is not None:
                result.conversation_id = conv.id
                if not g_in.blocked:  # blocked (e.g. injection) text is never stored or replayed as history
                    self._remember(conv, g_in.text, result)
            return result
        finally:
            outcome = result.kind if result else "error"
            CHAT_LATENCY.labels(outcome).observe(time.perf_counter() - started)
            self._audit.record(
                "chat.answer",
                user_id=user_id,
                outcome=outcome,
                scope=result.scope if result else None,
                triage=list(result.emergency.categories) if result and result.emergency else [],
                failed_checks=[k for k, v in (result.safety.checks.items() if result else []) if not v],
                citations=len(result.citations) if result else 0,
            )

    def rules_emergency_answer(self, question: str) -> ChatAnswer | None:
        """Emergency-only answer from the local red-flag rules (no model call, no memory), or None.
        Guarantees the emergency notice even when the request cannot be processed normally."""
        triage = self._triage.rules_only(question)
        if not triage.is_emergency:
            return None
        trace = AgentTrace()
        trace.step(
            "Triage agent (rules only)",
            "emergency - notice shown first",
            f"{', '.join(triage.categories)}; the full pipeline could not run for this request",
            "stop",
        )
        safety = SafetyInfo(
            triage_detectors=list(triage.detectors),
            red_flag_rules_version=triage.rules_version,
            trace=trace.steps,
        )
        REFUSALS.labels("emergency", "rules_only_fallback").inc()
        logger.warning(
            "emergency answered by rules-only fallback", extra={"categories": list(triage.categories)}
        )
        return self._build(
            "emergency", Scope.EMERGENCY, emergency=self._emergency_notice(triage), safety=safety
        )

    # ---- pipeline -----------------------------------------------------------------------------
    def audit_report(self, user_id: str, *, messages: int) -> None:
        self._audit.record("conversation.report", user_id=user_id, messages=messages)

    def audit_delete(self, user_id: str, *, conversations: int) -> None:
        self._audit.record("conversation.delete", user_id=user_id, count=conversations)

    def _remember(self, conv: Any, question: str, result: ChatAnswer) -> None:
        assert self._memory is not None
        reply = (
            result.answer
            or " ".join(result.preface)
            or (result.emergency.message if result.emergency else "")
        )
        try:
            self._memory.record(conv, "user", question)
            meta = {
                "kind": result.kind,
                "scope": result.scope,
                # For the evidence report: provenance only (titles, publishers, dates), no passage text.
                "citations": json.dumps([c.model_dump(exclude_none=True) for c in result.citations]),
                "limitations": result.limitations or "",
                "warnings": " ".join(result.warnings),
            }
            self._memory.record(conv, "assistant", reply, meta)
        except Exception as exc:  # memory problems must never hide an answer (or an emergency notice)
            logger.warning("conversation memory write failed", extra={"error": type(exc).__name__})

    def _answer(
        self,
        q_raw: str,
        g_in: GuardResult,
        filters: SearchFilter,
        history: list[tuple[str, str]],
        user_id: str,
        research: bool,
        capture: list[Passage] | None = None,
        phase: Callable[[str], None] = lambda _name: None,
        trace: AgentTrace | None = None,
    ) -> ChatAnswer:
        trace = trace or AgentTrace()
        q = g_in.text  # redacted question: the only form that reaches models, caches and storage
        # 1. urgent symptoms first, always: rules on the raw text (local), the LLM only sees redacted text
        triage = self._triage.assess(q_raw, llm_text=q)
        emergency = self._emergency_notice(triage) if triage.is_emergency else None
        llm_note = "" if triage.llm_ok else " (LLM unavailable - rules applied)"
        if triage.crisis:
            trace.step(
                "Triage agent",
                "crisis support",
                "detected by " + "+".join(triage.detectors) + llm_note,
                "stop",
            )
        elif triage.is_emergency:
            trace.step(
                "Triage agent",
                "emergency - notice shown first",
                f"{', '.join(triage.categories)} (by {'+'.join(triage.detectors)}){llm_note}",
                "stop",
            )
        else:
            trace.step(
                "Triage agent",
                "no red-flag pattern matched",
                f"rules + LLM second opinion{llm_note}. This is not an assessment: if you feel unwell or "
                f"symptoms get worse, call {self._contacts.emergency_number}.",
            )
        safety = SafetyInfo(
            triage_detectors=list(triage.detectors), red_flag_rules_version=triage.rules_version
        )

        if triage.crisis:
            # Self-harm: lead with crisis support; no generated content that could bury or soften it.
            REFUSALS.labels("emergency", "crisis").inc()
            return self._build("emergency", Scope.EMERGENCY, emergency=emergency, safety=safety)

        safety.guardrails = [f"input:{e.rule}:{e.action.name.lower()}" for e in g_in.events]
        if g_in.blocked:
            REFUSALS.labels("input", "guardrail").inc()
            reason = T.too_long() if g_in.has("length") else T.injection_refusal()
            kind = "emergency" if emergency else "refusal"
            return self._build(kind, Scope.OUT_OF_SCOPE, emergency=emergency, preface=[reason], safety=safety)

        decision = self._scope.classify(q)  # 2. scope before retrieval
        scope = decision.scope
        llm_txt = decision.llm_scope.value if decision.llm_scope else "unavailable"
        trace.step(
            "Scope agent",
            scope.value.replace("_", " "),
            f"rules: {decision.rules_scope.value}, LLM: {llm_txt} - stricter wins",
            "stop"
            if scope in (Scope.UNSAFE, Scope.OUT_OF_SCOPE)
            else ("warn" if scope in (Scope.PRESCRIBING_OR_DOSING, Scope.PERSONAL_DIAGNOSIS) else "ok"),
        )
        if scope is Scope.EMERGENCY and emergency is None:
            # The scope classifier spotted urgency the triage step missed: still lead with emergency advice.
            emergency = self._emergency_notice(
                TriageResult(is_emergency=True, categories=("other",), detectors=("scope",))
            )
            safety.triage_detectors.append("scope")

        if scope is Scope.UNSAFE:
            REFUSALS.labels(scope.value, "unsafe").inc()
            return self._build(
                "refusal",
                scope,
                emergency=emergency,
                preface=[T.unsafe_refusal(self._contacts)],
                safety=safety,
            )
        if scope is Scope.OUT_OF_SCOPE:
            return self._build(
                "redirect", scope, emergency=emergency, preface=[T.out_of_scope_redirect()], safety=safety
            )

        # Answer cache: only ever holds clean, non-emergency, first-turn answers (see AnswerCache.cacheable).
        cache_key = None
        if self._cache is not None and not history and not research and emergency is None:
            cache_key = self._cache.key(q, scope.value, filters, user_id)
            hit = self._cache.get(cache_key)
            trace.step(
                "Answer cache", "hit - verified answer reused" if hit else "miss", "", "ok" if hit else "skip"
            )
            if hit is not None:
                return hit.model_copy(update={"request_id": request_id_var.get(), "cached": True})

        # 3. retrieve -> generate (grounded); research mode only changes how evidence is gathered
        mode = _MODE_FOR_SCOPE[scope]
        graph = self._research_graph if research and self._research_graph is not None else self._graph
        phase("searching")
        try:
            state: dict[str, Any] = {}
            inputs = {"question": q, "mode": mode, "k": self._top_k, "filters": filters, "history": history}
            trace.restart_clock()
            for update in graph.stream(inputs, stream_mode="updates"):
                for node, delta in update.items():
                    state.update(delta or {})
                    self._trace_node(trace, node, delta or {}, history, research)
                    if node == "retrieve":
                        phase("generating")
        except Exception as exc:
            if emergency is not None:
                logger.warning(
                    "pipeline failed on an emergency path; notice kept", extra={"error": type(exc).__name__}
                )
                # Provider down must never hide the emergency message.
                logger.warning("generation failed; returning emergency notice only")
                return self._build("emergency", scope, emergency=emergency, safety=safety)
            raise

        passages: list[Passage] = state.get("passages") or []
        if capture is not None:
            capture.extend(passages)
        dosing = scope is Scope.PRESCRIBING_OR_DOSING
        if state.get("not_covered"):
            REFUSALS.labels(scope.value, "not_covered").inc()
            preface = [T.prescribing_refusal()] if dosing else []
            kind = "emergency" if emergency else ("refusal" if dosing else "not_covered")
            return self._build(
                kind, scope, emergency=emergency, preface=preface, answer=T.NOT_COVERED, safety=safety
            )

        phase("verifying")
        body, limitations = split_limitations(state["raw_answer"])

        # 4. output guardrails first: prompt leaks block; PHI and secrets are redacted, so the grounding
        #    checks below judge exactly the text the user would see.
        g_out = self._guard.check_output(body) if self._guard else GuardResult(text=body)
        safety.guardrails += [f"output:{e.rule}:{e.action.name.lower()}" for e in g_out.events]
        out_rules = ", ".join(sorted({e.rule for e in g_out.events}))
        trace.step(
            "Output guardrails",
            "blocked" if g_out.blocked else ("redacted" if g_out.events else "passed"),
            out_rules or "no prompt leak, personal data or secrets",
            "stop" if g_out.blocked else ("warn" if g_out.events else "ok"),
        )
        if g_out.blocked:
            REFUSALS.labels(scope.value, "output_guardrail").inc()
            kind = "emergency" if emergency else "refusal"
            return self._build(kind, scope, emergency=emergency, preface=[T.blocked_answer()], safety=safety)
        body = g_out.text

        high_risk = is_high_risk(q, scope.value)
        report = self._checker.run(body, passages, high_risk=high_risk)  # 5. post-answer safety checks
        safety.checks = {r.name.value: r.passed for r in report.results}
        safety.high_risk = high_risk
        checks_txt = ", ".join(f"{r.name.value} {'ok' if r.passed else 'FAILED'}" for r in report.results)
        judge_ran = any(r.name is CheckName.FAITHFULNESS for r in report.results)
        judge = " (faithfulness judge ran: high-risk topic)" if judge_ran else ""
        trace.step(
            "Verifier",
            "blocked - answer replaced by a refusal"
            if report.blocked
            else (
                "passed (diagnostic sentences removed)" if report.diagnosis_rewritten else "all checks passed"
            ),
            checks_txt + judge,
            "stop" if report.blocked else ("warn" if report.diagnosis_rewritten else "ok"),
        )

        if report.blocked:
            reason = report.blocked_by[0].value
            REFUSALS.labels(scope.value, reason).inc()
            preface = (
                [T.prescribing_refusal()]
                if dosing or CheckName.DOSING in report.blocked_by
                else [T.blocked_answer()]
            )
            return self._build(
                "emergency" if emergency else "refusal",
                scope,
                emergency=emergency,
                preface=preface,
                safety=safety,
            )

        preface: list[str] = []
        if scope is Scope.PERSONAL_DIAGNOSIS or report.diagnosis_rewritten:
            preface.append(T.diagnosis_referral())
        if dosing:
            preface.append(T.prescribing_cite_only_intro())

        cited_ids = sorted(n for n in citations_in(report.text) if 1 <= n <= len(passages))
        cited = {n: passages[n - 1] for n in cited_ids}
        stale = {p.id for p in stale_passages(list(cited.values()), self._stale_years, self._today)}

        warnings: list[str] = []
        if dosing or self._mentions_medicine(report.text):
            warnings.append(T.MEDICINE_CHANGE_WARNING)
        warnings.extend(apply_version_preference(passages)[1])  # versions of one guideline may conflict
        if stale:
            warnings.append(
                T.staleness_note(
                    sorted({p.title for p in cited.values() if p.id in stale}), self._stale_years
                )
            )

        citations = [self._citation(n, p, p.id in stale) for n, p in cited.items()]
        result = self._build(
            "emergency" if emergency else "answer",
            scope,
            emergency=emergency,
            preface=preface,
            answer=report.text,
            warnings=warnings,
            citations=citations,
            evidence_basis=self._evidence_basis(citations),
            limitations=self._safe_limitations(limitations, passages),
            safety=safety,
            research=research,
        )
        flagged = bool(g_in.events or g_out.events or any(p.extra.get("flagged") for p in passages))
        if (
            cache_key
            and self._cache is not None
            and self._cache.cacheable(result, flagged=flagged, has_history=bool(history))
        ):
            self._cache.put(cache_key, result)
        return result

    # ---- helpers ------------------------------------------------------------------------------
    @staticmethod
    def _trace_node(
        trace: AgentTrace, node: str, delta: dict[str, Any], history: list[tuple[str, str]], research: bool
    ) -> None:
        """Agent-trace entry per LangGraph node: counts and decisions only (no text)."""
        if node == "rewrite":
            n = len(delta.get("queries") or [])
            if history:
                trace.step(
                    "Query rewriter",
                    f"{n} search quer{'y' if n == 1 else 'ies'}",
                    "follow-up made standalone",
                )
            else:
                trace.step("Query rewriter", "skipped", "first question - no history", "skip")
        elif node == "retrieve":
            passages: list[Passage] = delta.get("passages") or []
            trusted = sum(p.trusted for p in passages)
            web = sum(p.doc_type == "web" for p in passages)
            user = len(passages) - trusted - web
            parts = (
                [f"{trusted} trusted"]
                + ([f"{user} your uploads"] if user else [])
                + ([f"{web} web"] if web else [])
            )
            superseded = sum(p.superseded for p in passages)
            agent = "Research agent (ReAct)" if research else "Retriever + re-ranker"
            detail = ", ".join(parts) + (f"; {superseded} older version(s) marked" if superseded else "")
            trace.step(
                agent,
                f"{len(passages)} passage(s) selected",
                detail if passages else "nothing relevant found",
                "ok" if passages else "warn",
            )
        elif node == "generate":
            if delta.get("not_covered"):
                trace.step(
                    "Answer agent",
                    "not covered",
                    "sources do not answer this - model memory never used",
                    "warn",
                )
            else:
                trace.step("Answer agent", "cited draft written", "only from the numbered passages")

    def _safe_limitations(self, text: str | None, passages: list[Passage]) -> str:
        """Model-written limitations are free text: keep them only if they pass the same output guardrails
        and diagnosis / dosing / number / drug-name checks as the answer; otherwise use the fixed wording."""
        if not text:
            return T.DEFAULT_LIMITATIONS
        if self._guard is not None and (
            self._guard.check_output(text).events
            or {"prompt_injection", "jailbreak"} & set(self._guard.check_document(text).rules)
        ):
            reason = "guardrails"
        elif any(is_diagnostic_sentence(s) for s in split_sentences(text)):
            reason = "diagnosis"
        elif not check_dosing(text, passages, self._lexicon).passed:
            reason = "dosing"
        elif (
            not check_numbers(text, passages).passed
            or not check_drug_names(text, passages, self._lexicon).passed
        ):
            reason = "grounding"
        else:
            return text
        SAFETY_CHECK_FAILURES.labels("limitations").inc()
        logger.warning("model limitations replaced", extra={"reason": reason})
        return T.DEFAULT_LIMITATIONS

    def _mentions_medicine(self, text: str) -> bool:
        words = set(re.findall(r"[a-z][a-z-]+", text.lower()))
        return bool(words & self._lexicon or MED_CONTEXT_RE.search(text))

    def _emergency_notice(self, triage: TriageResult) -> EmergencyNotice:
        return EmergencyNotice(
            message=T.emergency_message(self._contacts),
            number=self._contacts.emergency_number,
            crisis_message=T.crisis_message(self._contacts) if triage.crisis else None,
            poison_message=T.poison_message(self._contacts) if triage.poison else None,
            categories=list(triage.categories),
        )

    @staticmethod
    def _citation(n: int, p: Passage, stale: bool) -> Citation:
        return Citation(
            n=n,
            url=p.extra.get("url"),
            title=p.title,
            publisher=p.publisher if p.trusted else f"{p.publisher} (user-provided)",
            source=p.source,
            location=p.location or None,
            publication_date=p.publication_date.isoformat() if p.publication_date else None,
            evidence_level=p.evidence_level,
            trusted=p.trusted,
            user_provided=not p.trusted,
            stale=stale,
            superseded=p.superseded,
            version=p.version,
        )

    @staticmethod
    def _evidence_basis(citations: list[Citation]) -> str | None:
        if not citations:
            return None
        parts = []
        for c in citations:
            loc = f", {c.location}" if c.location else ""
            parts.append(f"[{c.n}] {c.title} - {c.publisher}{loc} ({c.publication_date or 'undated'})")
        return "Evidence basis: " + "; ".join(parts)

    def _build(self, kind: str, scope: Scope, **fields: Any) -> ChatAnswer:
        return ChatAnswer(
            request_id=request_id_var.get(), kind=kind, scope=scope.value, disclaimer=T.DISCLAIMER, **fields
        )
