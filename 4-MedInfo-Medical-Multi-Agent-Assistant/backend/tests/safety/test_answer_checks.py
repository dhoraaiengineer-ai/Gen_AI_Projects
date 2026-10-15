"""Release blocker: post-answer checks block unquoted doses, diagnoses, uncited or ungrounded content."""

from __future__ import annotations

from datetime import date

import pytest

from app.rag.interfaces import Passage
from app.safety.answer_checks import (
    AnswerChecker,
    CheckName,
    FaithfulnessJudge,
    check_citations,
    check_dosing,
    check_drug_names,
    check_numbers,
    is_diagnostic_sentence,
    is_high_risk,
    load_lexicon,
    stale_passages,
)
from tests.fakes import FakeChatModel

pytestmark = pytest.mark.safety

LEX = load_lexicon()
LABEL = Passage(
    id="p1",
    text="The usual starting dose of Zentoril is 10 mg once daily. Do not stop taking Zentoril suddenly.",
    source="synthetic/label.pdf",
    publisher="Synthetic Board",
    title="Zentoril Label (SYNTHETIC)",
    publication_date=date(2023, 6, 15),
)
GUIDE = Passage(
    id="p2",
    text="Hypertension is defined as a clinic blood pressure of 140/90 mmHg or higher.",
    source="synthetic/guide.pdf",
    publisher="Synthetic Board",
    title="Hypertension (SYNTHETIC)",
    publication_date=date(2012, 1, 1),
)
PASSAGES = [LABEL, GUIDE]


class TestDosing:
    def test_quoted_and_cited_dose_passes(self) -> None:
        body = 'The label states "The usual starting dose of Zentoril is 10 mg once daily" [1].'
        assert check_dosing(body, PASSAGES, LEX).passed

    @pytest.mark.parametrize(
        "body",
        [
            "You can take 20 mg of Zentoril daily [1].",  # dose not in a quote
            'The label states "The usual starting dose of Zentoril is 20 mg once daily" [1].',  # altered quote
            'The label states "The usual starting dose of Zentoril is 10 mg once daily".',  # no citation
            'The label states "The usual starting dose of Zentoril is 10 mg once daily" [2].',  # wrong passage
            'It says "The usual starting dose of Zentoril is 10 mg once daily" [1], so increase your dose to 20 mg.',
            "You should stop taking your medicine if it causes side effects [1].",  # change wording, unquoted
        ],
    )
    def test_unquoted_or_altered_dosing_blocked(self, body: str) -> None:
        assert not check_dosing(body, PASSAGES, LEX).passed

    def test_non_medicine_stop_wording_is_fine(self) -> None:
        assert check_dosing("Stopping smoking is recommended [2].", PASSAGES, LEX).passed


class TestDiagnosis:
    @pytest.mark.parametrize(
        "sentence",
        [
            "You have hypertension.",
            "You probably have type 2 diabetes [1].",
            "This sounds like asthma [1].",
            "Your symptoms suggest an infection.",
            "You're diabetic based on this.",
            "I think you have a heart condition.",
            "It is most likely a migraine.",
        ],
    )
    def test_diagnostic_phrasing_detected(self, sentence: str) -> None:
        assert is_diagnostic_sentence(sentence)

    @pytest.mark.parametrize(
        "sentence",
        [
            "If you have chest pain, call emergency services [1].",
            "When you have a cold, rest is advised [1].",
            "Hypertension often causes no symptoms [1].",
            "People who have diabetes may feel thirsty [1].",
            "You may have heard of HbA1c tests [1].",
        ],
    )
    def test_general_information_not_flagged(self, sentence: str) -> None:
        assert not is_diagnostic_sentence(sentence)

    def test_checker_removes_diagnosis_sentences(self) -> None:
        checker = AnswerChecker(LEX, FaithfulnessJudge(FakeChatModel()))
        report = checker.run(
            "You have hypertension. Hypertension is defined as a clinic blood pressure of 140/90 mmHg or higher [2].",
            PASSAGES,
            high_risk=False,
        )
        assert report.diagnosis_rewritten
        assert "You have" not in report.text
        assert not report.blocked


class TestGrounding:
    def test_uncited_sentence_fails(self) -> None:
        assert not check_citations("Hypertension is common.", 2).passed

    def test_citation_out_of_range_fails(self) -> None:
        assert not check_citations("Hypertension is common [3].", 2).passed

    def test_not_covered_sentence_needs_no_citation(self) -> None:
        body = "Hypertension is raised blood pressure [2]. Treatment is not covered by the available sources."
        assert check_citations(body, 2).passed

    def test_number_not_in_passages_fails(self) -> None:
        assert not check_numbers("The threshold is 150/95 mmHg [2].", PASSAGES).passed
        assert check_numbers("The threshold is 140/90 mmHg [2].", PASSAGES).passed

    def test_drug_name_not_in_passages_fails(self) -> None:
        assert not check_drug_names("Ibuprofen may help [1].", PASSAGES, LEX).passed
        assert check_drug_names("Zentoril is described [1].", PASSAGES, LEX).passed


class TestFaithfulnessAndStaleness:
    def test_high_risk_detection(self) -> None:
        assert is_high_risk("Can I take Zentoril while pregnant?", "info")
        assert is_high_risk("Fevadol for children?", "info")
        assert is_high_risk("anything", "prescribing_or_dosing")
        assert not is_high_risk("What is hypertension?", "info")

    def test_judge_failure_blocks_high_risk(self) -> None:
        checker = AnswerChecker(LEX, FaithfulnessJudge(FakeChatModel(judge='{"faithful": false}')))
        body = "Hypertension is defined as a clinic blood pressure of 140/90 mmHg or higher [2]."
        assert CheckName.FAITHFULNESS in checker.run(body, PASSAGES, high_risk=True).blocked_by

    def test_judge_error_fails_closed(self) -> None:
        checker = AnswerChecker(LEX, FaithfulnessJudge(FakeChatModel(judge=RuntimeError("down"))))
        body = "Hypertension is defined as a clinic blood pressure of 140/90 mmHg or higher [2]."
        assert checker.run(body, PASSAGES, high_risk=True).blocked

    def test_judge_not_called_for_low_risk(self) -> None:
        model = FakeChatModel()
        checker = AnswerChecker(LEX, FaithfulnessJudge(model))
        checker.run(
            "Hypertension is defined as a clinic blood pressure of 140/90 mmHg or higher [2].",
            PASSAGES,
            high_risk=False,
        )
        assert model.count("judge") == 0

    def test_stale_sources_flagged(self) -> None:
        stale = stale_passages(PASSAGES, 5, today=date(2026, 10, 14))
        assert [p.id for p in stale] == ["p2"]


class TestLimitationsParsing:
    @pytest.mark.parametrize(
        "raw",
        [
            "Fact one [1]. Fact two [1].\nLIMITATIONS: Not treatment.",
            "Fact one [1]. Fact two [1]. LIMITATIONS: Not treatment.",  # inline (seen live)
            "Fact one [1]. Fact two [1].\n\n**Limitations:** Not treatment.",
        ],
    )
    def test_limitations_split_inline_or_own_line(self, raw: str) -> None:
        from app.rag.prompts import split_limitations

        body, lim = split_limitations(raw)
        assert body == "Fact one [1]. Fact two [1]."
        assert lim == "Not treatment."
        assert check_citations(body, 1).passed

    def test_no_limitations_line(self) -> None:
        from app.rag.prompts import split_limitations

        assert split_limitations("Fact [1].") == ("Fact [1].", None)


class TestQuoteSpanningSentences:
    def test_split_keeps_multi_sentence_quote_together(self) -> None:
        from app.safety.text import split_sentences

        body = 'The label states "First part. Second part" [1]. Next fact [2].'
        assert split_sentences(body) == ['The label states "First part. Second part" [1].', "Next fact [2]."]

    def test_multi_sentence_quote_passes_dosing_check(self) -> None:
        body = (
            'The label states "The usual starting dose of Zentoril is 10 mg once daily. '
            'Do not stop taking Zentoril suddenly" [1].'
        )
        assert check_dosing(body, PASSAGES, LEX).passed

    def test_live_dosing_answer_shape_is_accepted(self) -> None:
        """Regression: the cite-only shape EURI produced live, against the real SYNTHETIC label text."""
        from app.config import PROJECT_ROOT
        from app.rag.retrieval import load_corpus

        corpus = load_corpus(PROJECT_ROOT / "data" / "synthetic" / "stage1_corpus.json")
        label = next(p for p in corpus if p.id == "sg-zen-001")
        body = (
            'The Zentoril Tablets Product Label states "The usual starting dose of Zentoril is 10 mg once daily. '
            'The dose may be increased to 20 mg once daily by the prescriber after 4 weeks" [1]. '
            'The label also states "Do not stop taking Zentoril suddenly without talking to your prescriber" [1]. '
            "The rest of this question is not covered by the available sources."
        )
        checker = AnswerChecker(LEX, FaithfulnessJudge(FakeChatModel()))
        report = checker.run(body, [label], high_risk=True)
        assert not report.blocked, report.results

    def test_paraphrased_gap_sentence_with_dose_wording_still_blocked(self) -> None:
        body = (
            'The label states "The usual starting dose of Zentoril is 10 mg once daily" [1]. '
            "The label does not mention doubling the dose on your own."
        )
        assert not check_dosing(body, PASSAGES, LEX).passed


def test_numbers_from_passage_header_are_grounded_but_invented_ones_are_not() -> None:
    v3 = Passage(
        id="v3",
        text="Hypertension is 140/90 mmHg or higher.",
        source="s",
        publisher="P",
        title="Guideline v3 (SYNTHETIC)",
        version="3.0",
        publication_date=date(2024, 3, 1),
    )
    assert check_numbers("Version 3 from 2024 uses 140/90 mmHg [1].", [v3]).passed
    assert not check_numbers("Version 4 uses 140/90 mmHg [1].", [v3]).passed
