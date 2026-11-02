from __future__ import annotations

import pytest

from app.rag import safety


@pytest.mark.parametrize(
    "question",
    [
        "How do I turn off the airbag light?",
        "how can I disable the ABS",
        "Is there a way to bypass the immobiliser?",
        "DPF delete instructions please",
        "how do I remove the EGR valve so it stops clogging and delete it",
        "Can I unplug the seat belt reminder chime?",
        "make the airbag light go off without fixing it",
        "AdBlue emulator for my Terra",
    ],
)
def test_bypass_requests_detected(question: str) -> None:
    assert safety.classify_question(question).bypass_request


@pytest.mark.parametrize(
    "question",
    [
        "What does the airbag light mean?",
        "When should I replace the brake fluid?",
        "What does the DPF light mean?",
        "What tyre pressure should I use?",
    ],
)
def test_ordinary_safety_questions_are_not_bypass(question: str) -> None:
    assert not safety.classify_question(question).bypass_request


@pytest.mark.parametrize(
    "question", ["How do I open the EV battery pack?", "Can I repair the high voltage cable myself?"]
)
def test_hv_diy_detected(question: str) -> None:
    assert safety.classify_question(question).hv_diy_request


def test_safety_systems_and_active_symptoms() -> None:
    q = safety.classify_question("Can I keep driving with the brake light on?")
    assert "brakes" in q.systems and q.active_symptom and q.safety_topic
    plain = safety.classify_question("What tyre pressure should I use?")
    assert "tyres_wheels" in plain.systems and not plain.active_symptom


@pytest.mark.parametrize(
    ("text", "hits"),
    [
        ("Your car is safe to drive.", ["safe to drive"]),
        ("It is probably fine.", ["probably fine"]),
        ("Do not continue driving. Contact service.", []),
        ("It is not safe to drive until inspected.", []),
        ("You should never keep driving with this light.", []),
        ("This looks like fraud.", ["fraud"]),
    ],
)
def test_forbidden_phrases_respect_negation(text: str, hits: list[str]) -> None:
    assert safety.forbidden_phrases_in(text) == hits


@pytest.mark.parametrize(
    ("role", "topic", "stop", "active", "tier"),
    [
        ("vehicle_owner", False, False, False, "none"),
        ("vehicle_owner", True, False, False, "info"),
        ("vehicle_owner", True, False, True, "stop"),
        ("vehicle_owner", False, True, False, "stop"),
        ("technician", True, False, False, "technician"),
        ("service_advisor", False, False, False, "none"),
    ],
)
def test_banner_tier_table(role: str, topic: bool, stop: bool, active: bool, tier: str) -> None:
    assert safety.banner_tier(role=role, safety_topic=topic, stop_required=stop, active_symptom=active) == tier


def test_required_action_is_verbatim_sentence() -> None:
    chunk = "§ 3.2 Brake light\nMeaning: low fluid.\nRequired action: Stop safely when it is\nsafe to do so. Call us."
    assert safety.required_action(chunk) == "Stop safely when it is safe to do so. Call us."
    assert safety.required_action("no action here") is None


def test_banner_texts_match_rules_55() -> None:
    assert safety.banner_text("stop") == safety.TEXTS["safety.banner.owner.stop"]
    assert safety.banner_text("none") is None
    assert "certified technician" in safety.TEXTS["safety.escalation"]


@pytest.mark.parametrize(
    "question",
    ["There is smoke and a burning smell coming from under my car.", "I hear hissing from the battery area"],
)
def test_thermal_symptoms_are_safety_topics_with_active_symptom(question: str) -> None:
    """Regression for eval saf-003: smoke must trigger the stop banner even when no manual passage is retrieved."""
    q = safety.classify_question(question)
    assert "fire_thermal" in q.systems and q.active_symptom
    assert safety.banner_tier(role="vehicle_owner", safety_topic=q.safety_topic, stop_required=False,
                              active_symptom=q.active_symptom) == "stop"  # fmt: skip
