import json

import pytest
from langchain_core.documents import Document

from app.rag.golden import (
    GoldenGenerator,
    GoldenItem,
    InMemoryGoldenStore,
    contains,
    parse_json_array,
    select_passages,
)
from tests.conftest import fake_llm

PASSAGES = [
    Document("The Eiffel Tower is 330 metres tall.", metadata={"source": "paris.pdf", "page": "2"}),
    Document("The Louvre opened in 1793.", metadata={"source": "paris.pdf", "page": "5"}),
]


def _pairs(*pairs: dict[str, object]) -> str:
    return "```json\n" + json.dumps(list(pairs)) + "\n```"


def test_generator_keeps_pairs_whose_evidence_is_in_the_passage() -> None:
    response = _pairs(
        {
            "question": "How tall is the Eiffel Tower?",
            "answer": "330 m",
            "evidence": "is 330 metres tall",
            "passage": 1,
        },
        {"question": "When did the Louvre open?", "answer": "1793", "evidence": "opened in 1793", "passage": 2},
    )
    items = GoldenGenerator(fake_llm(response), per_document=5).generate("paris.pdf", PASSAGES)

    assert [(i.question, i.answer, i.location, i.origin) for i in items] == [
        ("How tall is the Eiffel Tower?", "330 m", "p. 2", "generated"),
        ("When did the Louvre open?", "1793", "p. 5", "generated"),
    ]


def test_generator_drops_invented_evidence_bad_indexes_and_malformed_pairs() -> None:
    response = _pairs(
        {"question": "How tall is it?", "answer": "500 m", "evidence": "is 500 metres tall", "passage": 1},
        {"question": "When did the Louvre open?", "answer": "1793", "evidence": "opened in 1793", "passage": 9},
        {"question": "Missing fields"},
        {"question": "When did the Louvre open?", "answer": "1793", "evidence": "opened in 1793", "passage": 2},
    )
    items = GoldenGenerator(fake_llm(response), per_document=5).generate("paris.pdf", PASSAGES)
    assert [i.question for i in items] == ["When did the Louvre open?"]


def test_generator_caps_items_and_skips_the_llm_when_disabled() -> None:
    pair = {"question": "How tall is the tower?", "answer": "330 m", "evidence": "330 metres", "passage": 1}
    other = {"question": "When did the Louvre open?", "answer": "1793", "evidence": "1793", "passage": 2}
    assert len(GoldenGenerator(fake_llm(_pairs(pair, other)), per_document=1).generate("p", PASSAGES)) == 1
    assert GoldenGenerator(fake_llm(), per_document=0).generate("p", PASSAGES) == []  # no response scripted: no call


def test_parse_json_array_rejects_non_arrays() -> None:
    assert parse_json_array('Here you go: [{"a": 1}] thanks') == [{"a": 1}]
    with pytest.raises(ValueError):
        parse_json_array('{"a": 1}')


def test_contains_ignores_case_spacing_and_punctuation() -> None:
    assert contains("V olume : 52, Issue 8", "volume: 52 issue 8")
    assert not contains("anything", "   ")


def test_select_passages_spreads_across_the_document() -> None:
    docs = [Document(str(i)) for i in range(20)]
    assert [d.page_content for d in select_passages(docs, limit=4)] == ["0", "5", "10", "15"]


def test_store_replaces_generated_items_but_keeps_manual_ones() -> None:
    store = InMemoryGoldenStore()
    manual = GoldenItem.create("a.pdf", "Manual question?", "x", "evidence", None, "manual")
    old = GoldenItem.create("a.pdf", "Old generated?", "x", "evidence", None, "generated")
    other = GoldenItem.create("b.pdf", "Other doc?", "x", "evidence", None, "generated")
    store.upsert([manual, old, other])

    new = GoldenItem.create("a.pdf", "New generated?", "x", "evidence", None, "generated")
    store.replace_generated("a.pdf", [new])

    assert {i.question for i in store.list("a.pdf")} == {"Manual question?", "New generated?"}
    assert [i.question for i in store.list("b.pdf")] == ["Other doc?"]


def test_golden_ids_are_stable_per_source_and_question() -> None:
    a = GoldenItem.create("a.pdf", "Same question?", "x", "e", None, "manual")
    b = GoldenItem.create("a.pdf", "  same QUESTION?  ", "y", "e", None, "generated")
    assert a.id == b.id
    assert a.id != GoldenItem.create("b.pdf", "Same question?", "x", "e", None, "manual").id


def test_generator_drops_questions_that_mention_the_prompt_passages() -> None:
    response = _pairs(
        {"question": "What is described in passage 1?", "answer": "A tower", "evidence": "330 metres", "passage": 1},
        {"question": "When did the Louvre open?", "answer": "1793", "evidence": "opened in 1793", "passage": 2},
    )
    items = GoldenGenerator(fake_llm(response), per_document=5).generate("paris.pdf", PASSAGES)
    assert [i.question for i in items] == ["When did the Louvre open?"]
