"""Guardrail policy engine: applies policy.yaml at the input, document and output stages.
Pattern rules are deterministic and local (nothing leaves the process); paraphrases are covered by the
temperature-0 LLM classifiers in app/safety."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Literal

import yaml

from app.core.metrics import GUARDRAIL_EVENTS

logger = logging.getLogger(__name__)

POLICY_PATH = Path(__file__).with_name("policy.yaml")
Stage = Literal["input", "document", "output"]
SAFETY_ENFORCED = ("prescribing", "diagnosis")  # implemented in app/safety; must stay "block"
NEUTRALISED = "[instruction-like text removed]"


class Action(IntEnum):
    ALLOW = 0
    FLAG = 1
    REDACT = 2
    BLOCK = 3

    @classmethod
    def parse(cls, value: str) -> Action:
        return cls[value.strip().upper()]


@dataclass(frozen=True)
class GuardEvent:
    stage: str
    rule: str
    action: Action
    count: int


@dataclass
class GuardResult:
    text: str
    action: Action = Action.ALLOW
    events: list[GuardEvent] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.action is Action.BLOCK

    @property
    def rules(self) -> list[str]:
        return [e.rule for e in self.events]

    def has(self, rule: str) -> bool:
        return rule in self.rules


@dataclass(frozen=True)
class PiiEntity:
    name: str
    label: str
    patterns: tuple[re.Pattern[str], ...]


class PolicyError(ValueError):
    """The policy file is invalid or tries to weaken a safety-enforced rule."""


class PolicyEngine:
    def __init__(self, policy: dict[str, Any]) -> None:
        self.version = str(policy.get("version", "0"))
        self.max_input_chars = int(policy.get("limits", {}).get("max_input_chars", 4000))
        self._stages: dict[str, dict[str, Action]] = {
            stage: {rule: Action.parse(a) for rule, a in (rules or {}).items()}
            for stage, rules in policy.get("stages", {}).items()
        }
        for rule in SAFETY_ENFORCED:
            if self._stages.get("output", {}).get(rule) is not Action.BLOCK:
                raise PolicyError(f"output.{rule} is safety-enforced and must be 'block'")
        self._rules: dict[str, tuple[re.Pattern[str], ...]] = {
            name: tuple(re.compile(p, re.IGNORECASE) for p in patterns)
            for name, patterns in (policy.get("rules") or {}).items()
        }
        self._pii: list[PiiEntity] = []
        for name, spec in (policy.get("pii") or {}).items():
            flags = 0 if spec.get("flags") == "case_sensitive" else re.IGNORECASE
            self._pii.append(
                PiiEntity(name, spec["label"], tuple(re.compile(p, flags) for p in spec["patterns"]))
            )
        for stage, rules in self._stages.items():
            for rule in rules:
                if rule not in self._rules and rule not in {"pii", *SAFETY_ENFORCED}:
                    raise PolicyError(f"{stage}.{rule} has no patterns")

    @classmethod
    def load(cls, path: Path = POLICY_PATH) -> PolicyEngine:
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")))

    # ---- primitives -------------------------------------------------------------------------------
    def redact_pii(self, text: str) -> tuple[str, dict[str, int]]:
        counts: dict[str, int] = {}
        for entity in self._pii:
            for pattern in entity.patterns:

                def _sub(m: re.Match[str], label: str = entity.label) -> str:
                    if m.lastindex:  # replace only the captured value, keep the "MRN:" style prefix
                        start, end = m.span(1)
                        return m.group(0)[: start - m.start()] + label + m.group(0)[end - m.start() :]
                    return label

                text, n = pattern.subn(_sub, text)
                if n:
                    counts[entity.name] = counts.get(entity.name, 0) + n
        return text, counts

    def _matches(self, rule: str, text: str) -> list[re.Match[str]]:
        return [m for p in self._rules.get(rule, ()) for m in p.finditer(text)]

    @staticmethod
    def _neutralise_lines(text: str, matches: list[re.Match[str]]) -> str:
        """Replace every line that contains a match (documents: instruction-like lines)."""
        spans = [m.span() for m in matches]
        out, pos = [], 0
        for line in text.split("\n"):
            start, end = pos, pos + len(line)
            pos = end + 1
            hit = any(s < end and e > start for s, e in spans)
            out.append(NEUTRALISED if hit else line)
        return "\n".join(out)

    # ---- stages -----------------------------------------------------------------------------------
    def check(self, stage: Stage, text: str) -> GuardResult:
        result = GuardResult(text=text)
        rules = self._stages.get(stage, {})
        if stage == "input" and len(text) > self.max_input_chars:
            # Still redact: the text may reach the triage LLM or the rules-only emergency fallback.
            result.text, _ = self.redact_pii(text)
            self._record(result, stage, "length", Action.BLOCK, 1)
            return result
        for rule, action in rules.items():
            if rule in SAFETY_ENFORCED or action is Action.ALLOW:
                continue
            if rule == "pii":
                if action is Action.REDACT:
                    new_text, counts = self.redact_pii(result.text)
                    if counts:
                        result.text = new_text
                        self._record(result, stage, "pii", action, sum(counts.values()))
                else:
                    _, counts = self.redact_pii(result.text)
                    if counts:
                        self._record(result, stage, "pii", action, sum(counts.values()))
                continue
            matches = self._matches(rule, result.text)
            if not matches:
                continue
            if action is Action.REDACT:
                if stage == "document" and rule in {"prompt_injection", "jailbreak"}:
                    result.text = self._neutralise_lines(result.text, matches)
                else:
                    for p in self._rules[rule]:
                        result.text = p.sub("[REDACTED]", result.text)
            self._record(result, stage, rule, action, len(matches))
        return result

    def check_input(self, text: str) -> GuardResult:
        return self.check("input", text)

    def check_document(self, text: str) -> GuardResult:
        return self.check("document", text)

    def check_output(self, text: str) -> GuardResult:
        return self.check("output", text)

    @staticmethod
    def _record(result: GuardResult, stage: str, rule: str, action: Action, count: int) -> None:
        result.events.append(GuardEvent(stage, rule, action, count))
        result.action = max(result.action, action)
        GUARDRAIL_EVENTS.labels(stage=stage, rule=rule, action=action.name.lower()).inc()
        logger.info(
            "guardrail", extra={"stage": stage, "rule": rule, "action": action.name.lower(), "count": count}
        )
