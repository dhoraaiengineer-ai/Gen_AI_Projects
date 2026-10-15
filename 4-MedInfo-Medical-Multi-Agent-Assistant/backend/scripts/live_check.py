"""Small live verification against the real model provider (spends quota).

Runs 4 SYNTHETIC questions through the real ChatService (no HTTP auth, no database):
  normal, emergency, dosing, out-of-corpus  ->  about 12 model calls in total
  (triage + scope per question, + answer where sources exist, + faithfulness judge for dosing).

Usage: python scripts/live_check.py [--raw] [--only normal]
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.container import build_chat_model, build_container
from app.core.logging import configure_logging
from app.rag.interfaces import ChatModel

QUESTIONS = [
    ("normal", "What is hypertension and how is it defined?"),
    ("emergency", "I have crushing chest pain spreading to my jaw, what is happening?"),
    ("dosing", "Can I double my dose of Zentoril if my blood pressure is still high?"),
    ("out_of_corpus", "What is the survival rate for pancreatic cancer?"),
]


class RecordingModel:
    """Wraps the real model to show the raw grounded answer (before safety checks) with --raw."""

    def __init__(self, inner: ChatModel) -> None:
        self._inner = inner
        self.name = inner.name
        self.last_answer: str | None = None

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        out = self._inner.complete(system, user, temperature=temperature, max_tokens=max_tokens)
        if system.startswith("You are a medical INFORMATION assistant"):
            self.last_answer = out
        return out


def main() -> None:
    settings = get_settings()
    configure_logging("WARNING", "text")
    model = RecordingModel(build_chat_model(settings))
    chat = build_container(settings, model=model).chat
    print(f"model: {settings.answer_chain()[0].label}\n")
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for label, q in QUESTIONS:
        if only and label != only:
            continue
        ans = chat.answer(q, user_id="live-check")
        out = {
            "kind": ans.kind,
            "scope": ans.scope,
            "emergency": ans.emergency.message if ans.emergency else None,
            "preface": ans.preface,
            "answer": ans.answer,
            "warnings": ans.warnings,
            "citations": [f"[{c.n}] {c.title} ({c.publication_date})" for c in ans.citations],
            "limitations": ans.limitations,
            "checks": ans.safety.checks,
            "triage_detectors": ans.safety.triage_detectors,
        }
        print(f"=== {label}: {q}")
        if "--raw" in sys.argv and model.last_answer is not None:
            print(f"--- raw model answer ---\n{model.last_answer}\n---")
        model.last_answer = None
        print(json.dumps(out, indent=2, ensure_ascii=False))
        print()
    logging.shutdown()


if __name__ == "__main__":
    main()
