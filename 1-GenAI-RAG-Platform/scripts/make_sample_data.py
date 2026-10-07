"""Generate the synthetic "IoT RMS delay spread" sample dataset in every supported file format.

Everything here is fictional: the author, institute, journal, ISSN, DOI and all measurements. It mirrors
a real research-publication use case (a neural-network model of indoor radio delay spread) so the RAG
pipeline, citations and evaluation can be exercised without anyone's personal documents.

    .venv/Scripts/python scripts/make_sample_data.py   # writes data/sample/iot-delay-spread/

The golden Q&A for these files is data/golden/iot-delay-spread.json.
"""

import logging
from pathlib import Path

logger = logging.getLogger("make_sample_data")

OUT = Path(__file__).resolve().parent.parent / "data" / "sample" / "iot-delay-spread"

SYNTHETIC_NOTE = "Note: this is a synthetic document created to test the RAG platform. All names are fictional."

# ---------- shared facts (keep the golden dataset in sync with these) ----------

TITLE = "A Neural Network Model of RMS Delay Spread for Indoor Internet-of-Things Deployments"
AUTHOR = "Alex Morgan"
AFFILIATION = "Department of Electronics and Communication, Northbridge Institute of Technology, Riverton"
JOURNAL = "Journal of Applied Wireless Engineering"
ISSN = "2799-0417"
VOLUME_ISSUE = "Volume 14, Issue 3, March 2024"
DOI = "10.5555/jawe.2024.0317"
PAPER_URL = "https://example.org/jawe/2024/03/rms-delay-spread.pdf"

SUMMARY_TXT = f"""Project summary

{PAPER_URL}

Project title: "{TITLE}"
Author: {AUTHOR}, {AFFILIATION}.

This work was completed as the final-year research project of a Master of Technology programme.

Abstract
Internet-of-Things (IoT) devices deployed indoors need radio links that stay reliable in offices, corridors,
laboratories and warehouses. The root-mean-square (RMS) delay spread describes how much a transmitted signal
is smeared in time by multipath reflections, and it limits the symbol rate a link can support.
This project proposes a measurement-based RMS delay spread model built on a two-layer feedforward neural network.

The network takes five inputs: the transmitter-receiver distance, the carrier frequency, the antenna height,
the environment type, and the line-of-sight or non-line-of-sight (LOS/NLOS) condition.
It has a hidden layer of eight neurons and a single output neuron that predicts the mean RMS delay spread.
The hidden neurons use the hyperbolic tangent sigmoid activation function, and the network was trained with
the Levenberg-Marquardt backpropagation algorithm.

The residual between measured and predicted values is modelled as a random variable. Using maximum-likelihood
estimation, this shadowing term was found to follow a log-normal distribution.
Compared with the conventional log-distance delay spread model, the neural model reduced the prediction RMSE
from 9.8 ns to 4.1 ns on the held-out test sites.

The full paper was published in the {JOURNAL} (ISSN {ISSN}), {VOLUME_ISSUE}.

{SYNTHETIC_NOTE}
"""

CERTIFICATE_PAGES = [
    [
        "CERTIFICATE OF PUBLICATION",
        "",
        "This is to certify that the research article entitled",
        f'"{TITLE}"',
        "",
        f"authored by {AUTHOR},",
        f"{AFFILIATION},",
        "",
        f"has been published in the {JOURNAL}, ISSN {ISSN},",
        f"{VOLUME_ISSUE}.",
        "",
        "The journal is a peer-reviewed, open-access monthly publication",
        "of the Society for Wireless Systems Research.",
        "Journal impact factor: 4.21",
        "",
        "Issued by the Editorial Office, 18 March 2024.",
    ],
    [
        "PUBLICATION DETAILS",
        "",
        f"DOI: {DOI}",
        "Manuscript ID: JAWE-2023-1184",
        "Received: 2 November 2023",
        "Accepted after revision: 9 February 2024",
        "Published online: 15 March 2024",
        "Pages: 41-52",
        "Review process: double-blind, two reviewers",
        "Licence: Creative Commons Attribution 4.0 (CC BY 4.0)",
        "",
        SYNTHETIC_NOTE,
    ],
]

MEASUREMENTS = [
    [
        "Site",
        "Environment",
        "Frequency (GHz)",
        "Distance (m)",
        "Antenna height (m)",
        "Condition",
        "Mean RMS delay spread (ns)",
        "Std dev (ns)",
        "Samples",
    ],
    ["S1", "Office", 2.4, 5, 1.5, "LOS", 18.2, 3.1, 420],
    ["S1", "Office", 2.4, 15, 1.5, "NLOS", 31.7, 6.4, 410],
    ["S2", "Corridor", 2.4, 20, 2.0, "LOS", 24.5, 4.2, 380],
    ["S2", "Corridor", 5.8, 20, 2.0, "NLOS", 29.9, 5.8, 375],
    ["S3", "Laboratory", 5.8, 8, 1.2, "LOS", 15.6, 2.7, 450],
    ["S3", "Laboratory", 5.8, 12, 1.2, "NLOS", 27.3, 5.1, 440],
    ["S4", "Warehouse", 2.4, 30, 3.0, "LOS", 41.8, 7.9, 360],
    ["S4", "Warehouse", 2.4, 45, 3.0, "NLOS", 58.4, 11.2, 355],
    ["S5", "Lecture hall", 5.8, 18, 2.5, "LOS", 26.1, 4.6, 400],
    ["S5", "Lecture hall", 5.8, 25, 2.5, "NLOS", 37.5, 7.0, 395],
]

SITES = [
    ["Site", "Building type", "Floor area (m2)", "Construction", "Notes"],
    ["S1", "Office", 640, "Concrete and glass partitions", "Open-plan desks"],
    ["S2", "Corridor", 210, "Brick walls", "Long narrow corridor, metal doors"],
    ["S3", "Laboratory", 320, "Concrete", "Metal benches and equipment racks"],
    ["S4", "Warehouse", 2400, "Steel frame", "High shelving, the largest delay spreads"],
    ["S5", "Lecture hall", 900, "Concrete with wooden panels", "Tiered seating"],
]

FAQ_MD = f"""# Delay spread project FAQ

## What problem does the project solve?
It predicts the RMS delay spread of indoor radio channels so that IoT links can be planned without
measuring every building.

## Which frequency bands were measured?
Measurements were taken in the 2.4 GHz and 5.8 GHz bands at five indoor sites.

## How many measurement snapshots were collected?
A total of 3,985 channel snapshots were collected across the five sites.

## Which site had the largest delay spread?
The warehouse site (S4) had the largest delay spread, 58.4 ns in NLOS conditions, because of its steel frame
and high metal shelving.

## How was the data split for training?
Sites S1, S2 and S3 were used for training and validation, and sites S4 and S5 were held out for testing.

## What software was used?
The network was built and trained in Python with PyTorch, using a custom Levenberg-Marquardt optimiser.

## Where can I read the paper?
The paper is available at {PAPER_URL} (DOI {DOI}).

{SYNTHETIC_NOTE}
"""


# ---------- writers ----------


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, pages: list[list[str]]) -> None:
    """Minimal multi-page text PDF (Helvetica, one line per entry) with no PDF-writer dependency."""
    page_ids = [4 + 2 * i for i in range(len(pages))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_id, lines in zip(page_ids, pages, strict=True):
        body = "BT /F1 12 Tf 16 TL 60 760 Td " + " ".join(f"({_pdf_escape(line)}) Tj T*" for line in lines) + " ET"
        stream = body.encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(out)


def write_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    measurements = workbook.active
    measurements.title = "Measurements"
    for row in MEASUREMENTS:
        measurements.append(row)
    sites = workbook.create_sheet("Sites")
    for row in SITES:
        sites.append(row)
    workbook.save(path)


def write_docx(path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("Model design and results", level=1)
    doc.add_paragraph(f"Project: {TITLE}.")

    doc.add_heading("Architecture", level=2)
    doc.add_paragraph(
        "The model is a two-layer feedforward neural network with five inputs, one hidden layer of eight "
        "neurons and one output neuron. Categorical inputs (environment type and LOS/NLOS condition) are "
        "one-hot encoded, and continuous inputs are scaled to the range -1 to 1."
    )
    doc.add_heading("Training", level=2)
    doc.add_paragraph(
        "Training used the Levenberg-Marquardt backpropagation algorithm with early stopping on a validation "
        "split. Training stopped after 64 epochs, when the validation error had not improved for 6 epochs."
    )
    settings = [
        ["Setting", "Value"],
        ["Hidden neurons", "8"],
        ["Activation", "Hyperbolic tangent sigmoid"],
        ["Training algorithm", "Levenberg-Marquardt"],
        ["Initial damping factor (mu)", "0.001"],
        ["Train / validation / test split", "70% / 15% / 15%"],
        ["Epochs until early stop", "64"],
    ]
    _docx_table(doc, settings)

    doc.add_heading("Results", level=2)
    doc.add_paragraph("Prediction error on the held-out test sites (S4 warehouse, S5 lecture hall):")
    results = [
        ["Model", "RMSE (ns)", "R squared"],
        ["Log-distance model (baseline)", "9.8", "0.71"],
        ["Neural network, 5 hidden neurons", "5.2", "0.88"],
        ["Neural network, 8 hidden neurons (proposed)", "4.1", "0.93"],
        ["Neural network, 12 hidden neurons", "4.4", "0.92"],
    ]
    _docx_table(doc, results)

    doc.add_heading("Limitations", level=2)
    doc.add_paragraph(
        "The model was validated only for the 2.4 GHz and 5.8 GHz bands and for buildings up to 2,400 square "
        "metres. Outdoor-to-indoor links and millimetre-wave frequencies are not covered."
    )
    doc.add_paragraph(SYNTHETIC_NOTE)
    doc.save(path)


def _docx_table(doc, rows: list[list[str]]) -> None:  # type: ignore[no-untyped-def]
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.cell(r, c).text = value


def write_pptx(path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches

    deck = Presentation()
    slides = [
        ("RMS delay spread for indoor IoT", f"{AUTHOR}\nNorthbridge Institute of Technology", "Introduce the project."),
        (
            "Motivation",
            "Multipath reflections smear indoor radio signals in time.\n"
            "Large delay spread forces lower data rates for IoT links.\n"
            "Measuring every building is too slow and expensive.",
            "Stress that planning tools need a quick delay spread estimate.",
        ),
        (
            "Method",
            "Five measurement sites, 2.4 GHz and 5.8 GHz.\n"
            "Two-layer feedforward network, eight hidden neurons.\n"
            "Levenberg-Marquardt training with early stopping.",
            "Mention the 3,985 channel snapshots.",
        ),
    ]
    for title, body, notes in slides:
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = body
        slide.notes_slide.notes_text_frame.text = notes

    results = deck.slides.add_slide(deck.slide_layouts[5])
    results.shapes.title.text = "Results on held-out sites"
    rows = [["Model", "RMSE (ns)"], ["Log-distance baseline", "9.8"], ["Proposed neural network", "4.1"]]
    shape = results.shapes.add_table(len(rows), 2, Inches(1), Inches(2), Inches(7), Inches(2))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            shape.table.cell(r, c).text = value
    results.notes_slide.notes_text_frame.text = "The error is cut by more than half."

    future = deck.slides.add_slide(deck.slide_layouts[1])
    future.shapes.title.text = "Future work"
    future.placeholders[1].text = (
        "Extend the model to 60 GHz millimetre-wave links.\n"
        "Add outdoor-to-indoor measurements.\n"
        "Deploy the model inside a network planning tool."
    )
    future.notes_slide.notes_text_frame.text = SYNTHETIC_NOTE
    deck.save(path)


SCANNED_NOTEBOOK = [
    "LAB NOTEBOOK - CALIBRATION LOG",
    "Date: 12 January 2024",
    "Channel sounder calibrated at 2.4 GHz and 5.8 GHz",
    "Back-to-back cable loss: 0.8 dB",
    "Reference antenna gain: 6 dBi",
    "Noise floor: -97 dBm",
    "Operator: J. Rivera",
]

SCANNED_CERTIFICATE = [
    "CALIBRATION CERTIFICATE",
    "Certificate No. CAL-2024-031",
    "Instrument: Vector network analyser VNA-7",
    "Calibrated by: Riverton Metrology Lab",
    "Valid until: 31 December 2024",
]


def write_scan(path: Path, lines: list[str]) -> None:
    """An image of a page (like a phone photo or a scanner output) with no text layer: only OCR can read it.
    Saved as PNG, or as an image-only PDF when the path ends in .pdf."""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=34)
    page = Image.new("RGB", (1240, 120 + 64 * len(lines)), (250, 249, 245))
    draw = ImageDraw.Draw(page)
    for i, line in enumerate(lines):
        draw.text((70, 60 + 64 * i), line, fill=(20, 20, 20), font=font)
    page.save(path, "PDF" if path.suffix == ".pdf" else "PNG", resolution=150)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "project-summary.txt").write_text(SUMMARY_TXT, encoding="utf-8")
    write_pdf(OUT / "publication-certificate.pdf", CERTIFICATE_PAGES)
    write_xlsx(OUT / "measurement-campaign.xlsx")
    write_docx(OUT / "model-design.docx")
    write_pptx(OUT / "project-presentation.pptx")
    (OUT / "faq.md").write_text(FAQ_MD, encoding="utf-8")
    write_scan(OUT / "scanned-lab-notebook.png", SCANNED_NOTEBOOK)
    write_scan(OUT / "scanned-calibration-certificate.pdf", SCANNED_CERTIFICATE)
    for path in sorted(OUT.iterdir()):
        logger.info("wrote %s (%d bytes)", path.relative_to(OUT.parent.parent.parent), path.stat().st_size)


if __name__ == "__main__":
    main()
