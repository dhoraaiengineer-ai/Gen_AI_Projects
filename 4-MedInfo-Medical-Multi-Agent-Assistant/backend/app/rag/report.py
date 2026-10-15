"""Evidence report: a downloadable Markdown summary of one conversation - each question, the answer,
the sources it was built from (title, publisher, date, location or URL), limitations and the fixed safety
wording. Built only from stored (already PHI-redacted) text; it adds no new medical content."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.rag.memory import Conversation, Message
from app.safety.templates import DISCLAIMER

HEADER_NOTE = (
    "Information only, not medical advice. This report restates answers generated from the cited "
    "sources; it is not a diagnosis or treatment plan. Discuss any medical decision with a qualified "
    "healthcare professional."
)


def _sources(meta: dict[str, str]) -> list[dict[str, object]]:
    try:
        items = json.loads(meta.get("citations", "[]"))
    except ValueError:
        return []
    return [i for i in items if isinstance(i, dict)]


def _md_escape(text: str) -> str:
    # Plain text in Markdown: neutralise characters that would create links/HTML when rendered.
    return text.replace("<", "&lt;").replace(">", "&gt;")


def build_markdown(conv: Conversation, messages: list[Message], emergency_number: str) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Evidence report: {_md_escape(conv.title)}",
        "",
        f"_Generated {now} by MedInfo Assistant. In an emergency call {emergency_number}._",
        "",
        f"> {HEADER_NOTE}",
        "",
    ]
    question_no = 0
    for msg in messages:
        if msg.role == "user":
            question_no += 1
            lines += [f"## Question {question_no}", "", _md_escape(msg.text), ""]
            continue
        kind = msg.meta.get("kind", "answer")
        lines += [
            f"### Answer ({kind.replace('_', ' ')})",
            "",
            _md_escape(msg.text) or "_No answer text._",
            "",
        ]
        sources = _sources(msg.meta)
        if sources:
            lines += ["**Sources**", ""]
            for s in sources:
                parts = [
                    str(s.get("publisher") or ""),
                    str(s.get("location") or ""),
                    str(s.get("publication_date") or "undated"),
                ]
                ref = str(s.get("url") or "")
                label = " - ".join(p for p in parts if p)
                tag = " (user-provided)" if s.get("user_provided") else ""
                lines.append(
                    f"- [{s.get('n')}] {_md_escape(str(s.get('title')))}{tag}: {_md_escape(label)}"
                    + (f" <{ref}>" if ref else "")
                )
            lines.append("")
        if msg.meta.get("limitations"):
            lines += [f"**Limitations:** {_md_escape(msg.meta['limitations'])}", ""]
        if msg.meta.get("warnings"):
            lines += [f"**Notes:** {_md_escape(msg.meta['warnings'])}", ""]
    lines += ["---", "", f"_{DISCLAIMER}_", ""]
    return "\n".join(lines)
