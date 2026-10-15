"""Regenerate the SYNTHETIC Stage 1 corpus (data/synthetic/stage1_corpus.json).

Everything here is fictional: a fictional publisher, fictional drugs (Zentoril, Fevadol, Respiclar,
Glucarex) and fictional doses. It exists only to exercise retrieval, citations and safety checks.
It is NOT medical guidance and contains no real patient data.

Usage: python scripts/make_stage1_corpus.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUT = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "stage1_corpus.json"
PUBLISHER = "Synthetic Health Guidance Board (SYNTHETIC)"
COMMON = {
    "publisher": PUBLISHER,
    "jurisdiction": "SYNTHETIC",
    "licence": "CC0 (synthetic test data)",
    "trusted": True,
}

PASSAGES = [
    {
        "id": "sg-htn-001",
        "source": "synthetic/guideline-hypertension-v3.pdf",
        "title": "Adult Hypertension Guideline v3 (SYNTHETIC)",
        "section": "1. What is hypertension",
        "page": 2,
        "publication_date": "2024-03-01",
        "version": "3.0",
        "evidence_level": "moderate",
        "doc_type": "guideline",
        "text": (
            "Hypertension means blood pressure that stays raised over time. In this guideline, hypertension is "
            "defined as a clinic blood pressure of 140/90 mmHg or higher on repeated readings. Hypertension often "
            "causes no symptoms, so regular measurement is the main way it is found. Long-term raised blood "
            "pressure increases the risk of heart attack, stroke and kidney disease."
        ),
    },
    {
        "id": "sg-htn-002",
        "source": "synthetic/guideline-hypertension-v3.pdf",
        "title": "Adult Hypertension Guideline v3 (SYNTHETIC)",
        "section": "3. Lifestyle measures",
        "page": 5,
        "publication_date": "2024-03-01",
        "version": "3.0",
        "evidence_level": "high",
        "doc_type": "guideline",
        "text": (
            "Lifestyle measures recommended for people with hypertension include reducing salt intake, regular "
            "physical activity of at least 150 minutes a week, limiting alcohol, and stopping smoking. The "
            "evidence that reducing salt lowers blood pressure is graded high in this guideline."
        ),
    },
    {
        "id": "sg-zen-001",
        "source": "synthetic/label-zentoril.pdf",
        "title": "Zentoril Tablets Product Label (SYNTHETIC)",
        "section": "4.2 Dosage",
        "page": 1,
        "publication_date": "2023-06-15",
        "version": "2.1",
        "evidence_level": "label",
        "doc_type": "drug_label",
        "text": (
            "Zentoril is a fictional medicine used in this synthetic label to lower blood pressure. The usual "
            "starting dose of Zentoril is 10 mg once daily. The dose may be increased to 20 mg once daily by the "
            "prescriber after 4 weeks. Do not stop taking Zentoril suddenly without talking to your prescriber."
        ),
    },
    {
        "id": "sg-zen-002",
        "source": "synthetic/label-zentoril.pdf",
        "title": "Zentoril Tablets Product Label (SYNTHETIC)",
        "section": "4.6 Pregnancy",
        "page": 2,
        "publication_date": "2023-06-15",
        "version": "2.1",
        "evidence_level": "label",
        "doc_type": "drug_label",
        "text": (
            "Zentoril should not be used during pregnancy. Women who become pregnant while taking Zentoril should "
            "contact their prescriber promptly so that an alternative can be considered."
        ),
    },
    {
        "id": "sg-fev-001",
        "source": "synthetic/label-fevadol.pdf",
        "title": "Fevadol Oral Suspension Product Label (SYNTHETIC)",
        "section": "4.2 Dosage in children",
        "page": 1,
        "publication_date": "2022-11-01",
        "version": "1.4",
        "evidence_level": "label",
        "doc_type": "drug_label",
        "text": (
            "Fevadol is a fictional fever-reducing medicine. For children aged 6 to 12 years the label dose is "
            "5 ml every 6 hours, with no more than 4 doses in 24 hours. Fevadol is not licensed for children under "
            "6 years in this synthetic label."
        ),
    },
    {
        "id": "sg-t2d-001",
        "source": "synthetic/guideline-type2-diabetes.pdf",
        "title": "Type 2 Diabetes Overview (SYNTHETIC)",
        "section": "Symptoms",
        "page": 1,
        "publication_date": "2025-01-20",
        "version": "1.0",
        "evidence_level": "moderate",
        "doc_type": "guideline",
        "text": (
            "Common symptoms of type 2 diabetes include feeling very thirsty, passing urine more often, tiredness "
            "and blurred vision. Many people have no symptoms at first. Diabetes is confirmed by blood tests such "
            "as HbA1c; symptoms alone cannot confirm it."
        ),
    },
    {
        "id": "sg-chest-001",
        "source": "synthetic/guideline-chest-pain.pdf",
        "title": "Acute Chest Pain Guidance (SYNTHETIC)",
        "section": "Urgent assessment",
        "page": 1,
        "publication_date": "2024-09-10",
        "version": "1.2",
        "evidence_level": "high",
        "doc_type": "guideline",
        "text": (
            "Chest pain that is crushing, spreads to the arm, jaw or back, or comes with breathlessness or "
            "sweating can be a sign of a heart attack and needs emergency assessment. People with these symptoms "
            "should call emergency services rather than travel by themselves."
        ),
    },
    {
        "id": "sg-asthma-001",
        "source": "synthetic/guideline-asthma-2014.pdf",
        "title": "Asthma Care Guideline 2014 (SYNTHETIC)",
        "section": "2. Reliever inhalers",
        "page": 4,
        "publication_date": "2014-05-01",
        "version": "1.0",
        "evidence_level": "low",
        "doc_type": "guideline",
        "text": (
            "Respiclar is a fictional reliever inhaler described in this synthetic guideline. Asthma symptoms "
            "include wheeze, cough, chest tightness and shortness of breath. The guideline states that people "
            "whose reliever inhaler is needed more than 3 times a week should have their asthma reviewed."
        ),
    },
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "notice": "SYNTHETIC test corpus. Fictional publisher, drugs and doses. Not medical guidance. No real patient data.",
        "passages": [{**COMMON, **p} for p in PASSAGES],
    }
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    logger.info("wrote %s passages to %s", len(PASSAGES), OUT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
