"""Guardrail engine: applies the policy (policy.yaml) at three stages.

input     -> user questions / research tasks, before memory, cache, retrieval or any LLM call
documents -> uploaded files, before chunking and embedding (indirect prompt injection, leaked secrets)
output    -> answers, before they are returned, cached or stored in memory

Every check that fires is counted in rag_guardrail_events_total{stage,check,action} and written to the
audit log, which is the monitoring side of the guardrails (Grafana panel + alert in monitoring/).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from prometheus_client import Counter
from pydantic import BaseModel, Field

from app.guardrails import detectors
from app.guardrails.detectors import Match

logger = logging.getLogger(__name__)
audit = logging.getLogger("app.audit")

GUARDRAIL_EVENTS = Counter("rag_guardrail_events_total", "Guardrail checks that fired", ["stage", "check", "action"])

Action = Literal["allow", "flag", "redact", "block"]
Stage = Literal["input", "documents", "output"]
DEFAULT_POLICY = Path(__file__).with_name("policy.yaml")


class InputPolicy(BaseModel):
    max_chars: int = Field(2000, ge=1)
    prompt_injection: Action = "block"
    jailbreak: Action = "block"
    pii: Action = "redact"
    secrets: Action = "block"
    blocked_topics: Action = "block"


class DocumentPolicy(BaseModel):
    prompt_injection: Action = "flag"
    jailbreak: Action = "flag"
    pii: Action = "allow"
    secrets: Action = "redact"


class OutputPolicy(BaseModel):
    pii: Action = "redact"
    secrets: Action = "redact"
    system_prompt_leak: Action = "block"
    blocked_terms: Action = "redact"


class GuardrailPolicy(BaseModel):
    version: int = 1
    refusal_message: str = "I can't help with that request."
    input: InputPolicy = InputPolicy()
    documents: DocumentPolicy = DocumentPolicy()
    output: OutputPolicy = OutputPolicy()
    pii_types: list[str] = ["email", "phone", "credit_card", "aadhaar", "pan", "ssn", "iban"]
    blocked_topics: dict[str, list[str]] = {}
    blocked_terms: list[str] = []


def load_policy(path: str | Path | None = None) -> GuardrailPolicy:
    """Load and validate the policy. A missing or invalid file fails at startup, not on a request."""
    source = Path(path) if path else DEFAULT_POLICY
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    policy = GuardrailPolicy.model_validate(data)
    logger.info("guardrail policy loaded", extra={"policy": str(source), "version": policy.version})
    return policy


@dataclass(frozen=True)
class Violation:
    stage: Stage
    check: str
    action: Action
    detail: str


@dataclass
class GuardrailResult:
    text: str  # possibly redacted
    blocked: bool = False
    violations: list[Violation] = field(default_factory=list)

    @property
    def flags(self) -> list[str]:
        return sorted({v.check for v in self.violations if v.action == "flag"})


def _redact(text: str, matches: list[Match]) -> str:
    for m in sorted(matches, key=lambda m: m.start, reverse=True):
        if m.end > m.start:
            text = text[: m.start] + f"[REDACTED:{m.kind}]" + text[m.end :]
    return text


def _preview(matches: list[Match]) -> str:
    """What fired, without echoing the sensitive value itself into logs."""
    kinds = sorted({m.kind for m in matches})
    return f"{len(matches)} match(es): {', '.join(kinds)}"


class Guardrails:
    def __init__(self, policy: GuardrailPolicy, prompt_fingerprints: list[str] | None = None):
        self.policy = policy
        self.prompt_fingerprints = prompt_fingerprints or []

    @property
    def refusal(self) -> str:
        return self.policy.refusal_message

    # ---------- stages ----------

    def check_input(self, text: str, user_id: str | None = None) -> GuardrailResult:
        p = self.policy.input
        result = GuardrailResult(text)
        if len(text) > p.max_chars:
            self._apply(result, "input", "length", "block", [], f"{len(text)} > {p.max_chars} characters")
            return self._log(result, user_id)
        topics = [
            m for topic, items in self.policy.blocked_topics.items() for m in detectors.phrases(topic, text, items)
        ]
        checks = [
            ("prompt_injection", p.prompt_injection, lambda t: detectors.prompt_injection(t)),
            ("jailbreak", p.jailbreak, lambda t: detectors.jailbreak(t)),
            ("secrets", p.secrets, lambda t: detectors.secrets(t)),
            ("blocked_topics", p.blocked_topics, lambda t: topics),
            ("pii", p.pii, lambda t: detectors.pii(t, self.policy.pii_types)),
        ]
        return self._log(self._run(result, "input", checks), user_id)

    def check_document(self, text: str, source: str | None = None) -> GuardrailResult:
        p = self.policy.documents
        checks = [
            ("prompt_injection", p.prompt_injection, lambda t: detectors.prompt_injection(t)),
            ("jailbreak", p.jailbreak, lambda t: detectors.jailbreak(t)),
            ("secrets", p.secrets, lambda t: detectors.secrets(t)),
            ("pii", p.pii, lambda t: detectors.pii(t, self.policy.pii_types)),
        ]
        return self._log(self._run(GuardrailResult(text), "documents", checks), None, source)

    def check_output(self, text: str, user_id: str | None = None) -> GuardrailResult:
        p = self.policy.output
        checks = [
            ("system_prompt_leak", p.system_prompt_leak, lambda t: detectors.prompt_leak(t, self.prompt_fingerprints)),
            ("secrets", p.secrets, lambda t: detectors.secrets(t)),
            (
                "blocked_terms",
                p.blocked_terms,
                lambda t: detectors.phrases("blocked_term", t, self.policy.blocked_terms),
            ),
            ("pii", p.pii, lambda t: detectors.pii(t, self.policy.pii_types)),
        ]
        result = self._run(GuardrailResult(text), "output", checks)
        if result.blocked:
            result.text = self.refusal
        return self._log(result, user_id)

    # ---------- internals ----------

    def _run(self, result: GuardrailResult, stage: Stage, checks: list) -> GuardrailResult:  # type: ignore[type-arg]
        for check, action, detect in checks:
            if action == "allow":
                continue
            matches = detect(result.text)
            if matches:
                self._apply(result, stage, check, action, matches, _preview(matches))
                if result.blocked:
                    break  # no point checking further: the request/document/answer is stopped
        return result

    @staticmethod
    def _apply(
        result: GuardrailResult, stage: Stage, check: str, action: Action, matches: list[Match], detail: str
    ) -> None:
        GUARDRAIL_EVENTS.labels(stage, check, action).inc()
        result.violations.append(Violation(stage, check, action, detail))
        if action == "block":
            result.blocked = True
        elif action == "redact":
            result.text = _redact(result.text, matches)

    @staticmethod
    def _log(result: GuardrailResult, user_id: str | None, source: str | None = None) -> GuardrailResult:
        for v in result.violations:
            audit.info(
                "guardrail triggered",
                extra={
                    "stage": v.stage,
                    "check": v.check,
                    "action": v.action,
                    "detail": v.detail,
                    "user_id": user_id,
                    "source": source,
                },
            )
        return result
