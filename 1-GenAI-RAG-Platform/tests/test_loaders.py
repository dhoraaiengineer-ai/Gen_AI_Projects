import pytest

from app.rag.loaders import UnsupportedFileError, load_file, markdown_table
from tests.builders import make_docx, make_pdf, make_pptx, make_xlsx


def test_pdf_becomes_one_section_per_page() -> None:
    loaded = load_file("report.PDF", make_pdf(["Revenue grew in March.", "Costs fell in April."]))

    assert [(s.text, s.metadata) for s in loaded.sections] == [
        ("Revenue grew in March.", {"page": "1"}),
        ("Costs fell in April.", {"page": "2"}),
    ]
    assert not loaded.tabular


def test_pdf_without_text_is_rejected() -> None:
    with pytest.raises(UnsupportedFileError, match="OCR"):
        load_file("scan.pdf", make_pdf([""]))


def test_xlsx_sheets_become_markdown_tables() -> None:
    data = make_xlsx({"Sales": [["Region", "Q1"], ["APAC", 120], [None, None], ["EMEA", 95.5]], "Empty": []})
    loaded = load_file("figures.xlsx", data)

    assert loaded.tabular
    assert [(s.text, s.metadata) for s in loaded.sections] == [
        ("| Region | Q1 |\n| --- | --- |\n| APAC | 120 |\n| EMEA | 95.5 |", {"sheet": "Sales"}),
    ]


def test_docx_keeps_headings_paragraphs_and_tables_in_order() -> None:
    data = make_docx("Leave policy", "Staff get 20 days a year.", [["Grade", "Days"], ["G1", "20"]])
    [section] = load_file("policy.docx", data).sections

    assert section.text == (
        "## Leave policy\n\nStaff get 20 days a year.\n\n| Grade | Days |\n| --- | --- |\n| G1 | 20 |"
    )


def test_pptx_one_section_per_slide_with_tables_and_notes() -> None:
    data = make_pptx("Roadmap", "Launch in May.", "Mention the beta.", [["Phase", "Month"], ["Beta", "April"]])
    sections = load_file("deck.pptx", data).sections

    assert [s.metadata for s in sections] == [{"slide": "1"}, {"slide": "2"}]
    assert sections[0].text == "Roadmap\n\nLaunch in May.\n\nSpeaker notes: Mention the beta."
    assert "| Phase | Month |\n| --- | --- |\n| Beta | April |" in sections[1].text


def test_csv_is_tabular_raw_text() -> None:
    loaded = load_file("people.csv", b"name,city\nAsha,Tokyo\n")
    assert loaded.tabular
    assert loaded.sections[0].text == "name,city\nAsha,Tokyo\n"


def test_text_files_decode_utf8_with_bom_and_fall_back_to_latin1() -> None:
    assert load_file("a.md", b"\xef\xbb\xbf# Caf\xc3\xa9").sections[0].text == "# Café"  # UTF-8 BOM + é
    assert load_file("b.txt", "Café".encode("latin-1")).sections[0].text == "Café"


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        ("old.xls", b"x", "save it as .xlsx"),
        ("old.doc", b"x", "save it as .docx"),
        ("tool.exe", b"x", "unsupported file type .exe"),
        ("noext", b"x", "unsupported file type (none)"),
        ("broken.pdf", b"not a pdf", "could not read the file"),
        ("blank.txt", b"   \n", "contains no text"),
    ],
)
def test_bad_files_are_rejected_with_a_clear_reason(filename: str, data: bytes, message: str) -> None:
    with pytest.raises(UnsupportedFileError, match=message.replace("(", r"\(").replace(")", r"\)")):
        load_file(filename, data)


def test_markdown_table_pads_ragged_rows_and_escapes_pipes() -> None:
    assert markdown_table([["a", "b"], ["x|y"]]) == "| a | b |\n| --- | --- |\n| x\\|y |  |"
    assert markdown_table([[None], []]) == ""
