"""Diagnosis node — deterministic pieces (no DB, no LLM)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidDtc
from app.graph.nodes.diagnosis import _ROUTINE_CLEAR, _SPEC_VALUE, DiagnosisDraft, validate_dtcs
from app.rag import safety


def test_dtc_format_normalised_and_deduplicated() -> None:
    assert validate_dtcs([" p0301", "P0301", "c0035", ""]) == ["P0301", "C0035"]


@pytest.mark.parametrize("bad", ["P03O1", "X0301", "P030", "P03011", "0301"])
def test_invalid_dtc_rejected(bad: str) -> None:
    with pytest.raises(InvalidDtc) as exc:
        validate_dtcs(["P0301", bad])
    assert exc.value.details == {"invalid": [bad.upper()]}


def test_empty_hypotheses_with_sufficient_evidence_is_malformed() -> None:
    with pytest.raises(ValidationError):
        DiagnosisDraft.model_validate({"hypotheses": [], "insufficient_evidence": False})
    assert DiagnosisDraft.model_validate({"hypotheses": [], "insufficient_evidence": True}).hypotheses == []


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Tighten to 28 N·m", True),
        ("disc below 20.0 mm", True),
        ("resistance 0.6 ohm", True),
        ("spread over 50 mV", True),
        ("soot load 45 g", True),
        ("Cylinder 1 misfire", False),
        ("between 100 and 120 km/h", False),
        ("model year 2023", False),
    ],
)
def test_spec_values_detected(text: str, found: bool) -> None:
    assert bool(_SPEC_VALUE.search(text)) is found


def test_routine_code_clearing_is_not_a_bypass_request() -> None:
    note = "Clear the codes, road test; the EGR fault returns."
    assert safety.classify_question(note).bypass_request  # the generic owner-facing pattern would refuse it
    assert not safety.classify_question(_ROUTINE_CLEAR.sub(" ", note)).bypass_request


@pytest.mark.parametrize(
    "text",
    [
        "Customer wants a DPF delete",
        "How do I disable the AdBlue system?",
        "delete the cat so the light goes off",
        "bypass the HV interlock",
        "Fit an EGR emulator",
        "Just disable ABS so the warning stops",
    ],
)
def test_bypass_requests_detected(text: str) -> None:
    assert safety.classify_question(_ROUTINE_CLEAR.sub(" ", text)).bypass_request


def test_quote_check_tolerates_typographic_lookalikes_only() -> None:
    from app.rag.answer import _norm

    source = "§ TSB-TR-2025-03 Corrosion on the hub face prevents the wheel seating flat, causing run-out."
    assert _norm("causing run\u2011out.") in _norm(source)  # non-breaking hyphen from the model
    assert _norm("causing run-off.") not in _norm(source)  # still a strict substring check


def test_passage_refs_stripped_from_prose_but_not_dtcs() -> None:
    from app.graph.nodes.diagnosis import _PASSAGE_REF

    assert _PASSAGE_REF.sub("", "C0035 and ABS light match C1: sensor (C2)") == "C0035 and ABS light match sensor"
