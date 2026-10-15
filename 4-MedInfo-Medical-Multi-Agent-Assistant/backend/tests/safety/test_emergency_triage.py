"""Release blocker: 100% of emergency vignettes must trigger the emergency message.
All vignettes are synthetic."""

from __future__ import annotations

import pytest

from app.safety.triage import RedFlagRules, TriageService
from tests.fakes import FakeChatModel

pytestmark = pytest.mark.safety

# (vignette, expected category) — the rules alone must catch these, with the LLM saying "not emergency".
EMERGENCY_VIGNETTES = [
    ("I have crushing chest pain going down my left arm", "chest_pain"),
    ("my dad has chest pressure and is sweating", "chest_pain"),
    ("there's a tightness across my chest since an hour", "chest_pain"),
    ("I think I'm having a heart attack", "chest_pain"),
    ("my mum's face is drooping on one side and her speech is slurred", "stroke"),
    ("he suddenly can't lift his right arm", "stroke"),
    ("sudden numbness on the left side of my body", "stroke"),
    ("I can't breathe properly and my lips are turning blue", "breathing"),
    ("my son is struggling to breathe", "breathing"),
    ("my throat is swelling after eating peanuts", "anaphylaxis"),
    ("allergic reaction and now I feel faint and wheezy", "anaphylaxis"),
    ("I used my EpiPen, what now?", "anaphylaxis"),
    ("there is heavy bleeding from a cut that won't stop", "heavy_bleeding"),
    ("my husband is vomiting blood", "heavy_bleeding"),
    ("my grandfather collapsed and is unresponsive", "unconscious_seizure"),
    ("my friend is having a seizure right now", "unconscious_seizure"),
    ("she's not breathing", "unconscious_seizure"),
    ("I want to kill myself", "self_harm"),
    ("I've been thinking about ending my life", "self_harm"),
    ("i dont want to live anymore", "self_harm"),
    ("Honestly I feel like everyone would be better off dead without me", "self_harm"),
    ("I took too many tablets tonight", "overdose_poisoning"),
    ("my toddler swallowed a button battery", "overdose_poisoning"),
    ("I think I overdosed on my pills", "overdose_poisoning"),
    ("high fever and a stiff neck since this morning", "meningitis_signs"),
    ("my child has a rash that doesn't fade under a glass", "meningitis_signs"),
    ("I'm 20 weeks pregnant and bleeding", "pregnancy_emergency"),
    ("severe abdominal pain and I'm pregnant", "pregnancy_emergency"),
    ("my 2 month old baby has a fever and is floppy", "infant_severe"),
    ("our newborn won't feed and seems limp", "infant_severe"),
    ("worst headache of my life came on suddenly", "sudden_severe_headache"),
    ("sudden severe headache like being hit on the head", "sudden_severe_headache"),
    ("I suddenly lost my vision in one eye", "sudden_severe_headache"),
]

# Paraphrases the rules may miss: the LLM second opinion must still trigger the message.
LLM_ONLY_VIGNETTES = [
    "my elderly neighbour went grey and keeps clutching his ribs, sweating buckets",
    "I've written goodbye letters to my family",
]

NON_EMERGENCY = [
    "What is hypertension?",
    "What are the lifestyle measures for high blood pressure?",
    "What does HbA1c measure?",
    "How is type 2 diabetes confirmed?",
]

NOT_EMERGENCY_LLM = '{"emergency": false, "category": "none", "self_harm": false}'


@pytest.fixture(scope="module")
def rules() -> RedFlagRules:
    return RedFlagRules.load()


@pytest.mark.parametrize(("question", "category"), EMERGENCY_VIGNETTES)
def test_rules_catch_every_emergency_vignette(rules: RedFlagRules, question: str, category: str) -> None:
    result = TriageService(rules, FakeChatModel(triage=NOT_EMERGENCY_LLM)).assess(question)
    assert result.is_emergency, question
    assert category in result.categories
    assert "rules" in result.detectors


@pytest.mark.parametrize(("question", "category"), EMERGENCY_VIGNETTES)
def test_rules_fire_even_when_llm_classifier_is_down(
    rules: RedFlagRules, question: str, category: str
) -> None:
    result = TriageService(rules, FakeChatModel(triage=RuntimeError("provider down"))).assess(question)
    assert result.is_emergency
    assert not result.llm_ok


@pytest.mark.parametrize("question", LLM_ONLY_VIGNETTES)
def test_llm_second_opinion_catches_paraphrases(rules: RedFlagRules, question: str) -> None:
    llm = FakeChatModel(triage='{"emergency": true, "category": "chest_pain", "self_harm": false}')
    result = TriageService(rules, llm).assess(question)
    assert result.is_emergency
    assert "llm" in result.detectors


def test_llm_self_harm_flag_sets_crisis(rules: RedFlagRules) -> None:
    llm = FakeChatModel(triage='{"emergency": true, "category": "self_harm", "self_harm": true}')
    result = TriageService(rules, llm).assess("I've written goodbye letters to my family")
    assert result.crisis
    assert "self_harm" in result.categories


def test_unknown_llm_category_is_bounded(rules: RedFlagRules) -> None:
    llm = FakeChatModel(triage='{"emergency": true, "category": "made-up-label-xyz", "self_harm": false}')
    result = TriageService(rules, llm).assess("something odd")
    assert result.categories == ("other",)


@pytest.mark.parametrize("question", NON_EMERGENCY)
def test_general_questions_do_not_trigger(rules: RedFlagRules, question: str) -> None:
    result = TriageService(rules, FakeChatModel(triage=NOT_EMERGENCY_LLM)).assess(question)
    assert not result.is_emergency


def test_rules_file_is_marked_unreviewed_until_clinician_signs_off(rules: RedFlagRules) -> None:
    # Guards against silently claiming clinical review.
    assert rules.status in {"draft_pending_clinician_review", "approved"}
