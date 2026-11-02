"""Deterministic safety layer (rules/55-automotive-safety.md). No LLM involvement.

Fixed texts are verbatim from rules/55 (i18n keys `safety.*`). Detection lists live in config/safety_keywords.yaml.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "config" / "safety_keywords.yaml"

BannerTier = Literal["none", "info", "stop", "technician"]

TEXTS: dict[str, str] = {
    "safety.banner.owner.info": (
        "⚠ Safety-related topic. This concerns a safety system. If a warning light is on or you notice a change in how "
        "the vehicle behaves, contact Veloxa service."
    ),
    "safety.banner.owner.stop": (
        "⚠ SAFETY-CRITICAL: Stop safely when it is safe to do so and contact Veloxa service or roadside assistance. "
        "Do not continue driving until a certified technician has inspected the vehicle."
    ),
    "safety.banner.technician": "⚠ Certified technician required — follow the cited procedure and PPE.",
    "safety.ev_hv.owner": (
        "High-voltage components must only be serviced by a certified HV technician. Do not open, probe, or repair "
        "them yourself."
    ),
    "safety.escalation": (
        "I recommend having this checked by a certified technician. Would you like me to book a service appointment?"
    ),
    "safety.bypass_refusal": (
        "I can't help with disabling or bypassing safety or emissions systems. If a warning light is on, a certified "
        "technician can diagnose the cause — would you like to book a visit?"
    ),
    "safety.ai_panel": "AI-generated preliminary assessment — not a decision.",
}

_NEGATION = re.compile(r"\b(not|never|n't|no longer|do not|don't|cannot|can't|shouldn't|should not)\s+(\w+\s+){0,2}$")


@dataclass(frozen=True)
class SafetyConfig:
    system_terms: dict[str, tuple[str, ...]]
    active_symptoms: tuple[str, ...]
    bypass: tuple[re.Pattern[str], ...]
    hv_diy: tuple[re.Pattern[str], ...]
    forbidden: tuple[str, ...]


@lru_cache
def load_config(path: Path = CONFIG) -> SafetyConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SafetyConfig(
        system_terms={k: tuple(v) for k, v in raw["safety_systems"].items()},
        active_symptoms=tuple(raw["active_symptoms"]),
        bypass=tuple(re.compile(p, re.IGNORECASE) for p in raw["bypass_patterns"]),
        hv_diy=tuple(re.compile(p, re.IGNORECASE) for p in raw["hv_diy_patterns"]),
        forbidden=tuple(raw["forbidden_phrases"]),
    )


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", text, re.IGNORECASE) is not None


@dataclass(frozen=True)
class QuestionSafety:
    systems: tuple[str, ...]
    active_symptom: bool
    bypass_request: bool
    hv_diy_request: bool

    @property
    def safety_topic(self) -> bool:
        return bool(self.systems) or self.hv_diy_request


def classify_question(question: str, cfg: SafetyConfig | None = None) -> QuestionSafety:
    cfg = cfg or load_config()
    systems = tuple(name for name, terms in cfg.system_terms.items() if any(_contains(question, t) for t in terms))
    return QuestionSafety(
        systems=systems,
        active_symptom=any(_contains(question, p) for p in cfg.active_symptoms),
        bypass_request=any(p.search(question) for p in cfg.bypass),
        hv_diy_request=any(p.search(question) for p in cfg.hv_diy),
    )


def forbidden_phrases_in(text: str, cfg: SafetyConfig | None = None) -> list[str]:
    """Forbidden phrases used affirmatively (a preceding negation such as 'do not continue driving' is allowed)."""
    cfg = cfg or load_config()
    hits = []
    for phrase in cfg.forbidden:
        for m in re.finditer(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", text, re.IGNORECASE):
            if not _NEGATION.search(text[: m.start()].lower()[-40:]):
                hits.append(phrase)
                break
    return hits


def banner_tier(*, role: str, safety_topic: bool, stop_required: bool, active_symptom: bool) -> BannerTier:
    """rules/55 tier table. When in doubt between info and stop → stop."""
    if role in ("technician", "service_advisor", "warranty_admin"):
        return "technician" if (safety_topic or stop_required) else "none"
    if stop_required or (safety_topic and active_symptom):
        return "stop"
    return "info" if safety_topic else "none"


def banner_text(tier: BannerTier) -> str | None:
    return {
        "none": None,
        "info": TEXTS["safety.banner.owner.info"],
        "stop": TEXTS["safety.banner.owner.stop"],
        "technician": TEXTS["safety.banner.technician"],
    }[tier]


_REQUIRED_ACTION = re.compile(r"Required action:\s*(.+?)(?:\n\s*\n|$)", re.DOTALL)


def required_action(chunk_text: str) -> str | None:
    """The manual's own 'Required action:' sentence(s), verbatim (whitespace-normalised)."""
    m = _REQUIRED_ACTION.search(chunk_text)
    return " ".join(m.group(1).split()) if m else None
