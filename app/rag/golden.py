"""Golden dataset: question / reference-answer pairs used to evaluate retrieval and answers.

Generated automatically by the LLM for every added or updated document, or imported by hand.
Each item carries a verbatim `evidence` quote from the source: evaluation checks whether retrieval
brings back a chunk containing it. Generated items whose evidence isn't really in the passage are
dropped, since the LLM made them up.
The Postgres store lives in providers.py; the in-memory one is for tests.
"""

import json
import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from langchain_core.documents import Document
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field, ValidationError

from app.rag.prompts import GOLDEN_SYSTEM_PROMPT, GOLDEN_USER_TEMPLATE
from app.rag.retriever import chunk_location

logger = logging.getLogger(__name__)

Origin = Literal["generated", "manual"]

# Bound the prompt: a few spread-out passages are enough for a handful of questions.
MAX_PASSAGES = 8
MAX_PASSAGE_CHARS = 1500

_ID_NAMESPACE = uuid.UUID("b0b3f1d2-6a4e-4d8a-9a57-1f2c3d4e5f60")


@dataclass(frozen=True)
class GoldenItem:
    id: str
    source: str
    question: str
    answer: str
    evidence: str
    location: str | None
    origin: Origin

    @classmethod
    def create(
        cls, source: str, question: str, answer: str, evidence: str, location: str | None, origin: Origin
    ) -> "GoldenItem":
        item_id = str(uuid.uuid5(_ID_NAMESPACE, f"{source}\x00{question.strip().lower()}"))
        return cls(item_id, source, question.strip(), answer.strip(), evidence.strip(), location, origin)


class GoldenStore(Protocol):
    def upsert(self, items: Sequence[GoldenItem]) -> None: ...

    def replace_generated(self, source: str, items: Sequence[GoldenItem]) -> None:
        """Swap a source's generated items for new ones; manual items are kept."""
        ...

    def list(self, source: str | None = None, limit: int | None = None) -> list[GoldenItem]: ...

    def delete_source(self, source: str) -> int:
        """Remove every item (generated and manual) for a deleted document."""
        ...


class InMemoryGoldenStore:
    def __init__(self) -> None:
        self.items: dict[str, GoldenItem] = {}

    def upsert(self, items: Sequence[GoldenItem]) -> None:
        self.items.update((item.id, item) for item in items)

    def replace_generated(self, source: str, items: Sequence[GoldenItem]) -> None:
        self.items = {k: v for k, v in self.items.items() if not (v.source == source and v.origin == "generated")}
        self.upsert(items)

    def delete_source(self, source: str) -> int:
        doomed = [k for k, v in self.items.items() if v.source == source]
        for key in doomed:
            del self.items[key]
        return len(doomed)

    def list(self, source: str | None = None, limit: int | None = None) -> list[GoldenItem]:
        items = [i for i in self.items.values() if source is None or i.source == source]
        return items[:limit] if limit else items


# Questions like "what does passage 3 say" are meaningless to someone who never saw the prompt.
_REFERS_TO_PROMPT = re.compile(r"\b(passages?|excerpts?|the (?:above|given) text)\b", re.IGNORECASE)


def normalize(text: str) -> str:
    """Case, whitespace and punctuation-insensitive form, so PDF extraction artifacts ("V olume") still match."""
    return re.sub(r"[\W_]+", "", text.lower())


def contains(haystack: str, needle: str) -> bool:
    return bool(needle.strip()) and normalize(needle) in normalize(haystack)


class _GeneratedPair(BaseModel):
    question: str = Field(min_length=5)
    answer: str = Field(min_length=1)
    evidence: str = Field(min_length=5)
    passage: int


def select_passages(chunks: Sequence[Document], limit: int = MAX_PASSAGES) -> list[Document]:
    """Spread picks across the document instead of only its beginning."""
    if len(chunks) <= limit:
        return list(chunks)
    step = len(chunks) / limit
    return [chunks[int(i * step)] for i in range(limit)]


def parse_json_array(text: str) -> list[object]:
    """Models sometimes wrap JSON in ```json fences or add a sentence around it."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("no JSON array in the response")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    return data


class GoldenGenerator:
    def __init__(self, llm: Runnable[LanguageModelInput, BaseMessage], per_document: int):
        self.llm = llm
        self.per_document = per_document

    def generate(self, source: str, chunks: Sequence[Document]) -> list[GoldenItem]:
        if self.per_document <= 0 or not chunks:
            return []
        passages = select_passages(chunks)
        rendered = "\n\n".join(
            f'<passage index="{i}">\n{doc.page_content[:MAX_PASSAGE_CHARS]}\n</passage>'
            for i, doc in enumerate(passages, start=1)
        )
        prompt = GOLDEN_USER_TEMPLATE.format(count=self.per_document, passages=rendered)
        response = self.llm.invoke([SystemMessage(GOLDEN_SYSTEM_PROMPT), HumanMessage(prompt)])

        items: list[GoldenItem] = []
        for raw in parse_json_array(str(response.content)):
            try:
                pair = _GeneratedPair.model_validate(raw)
            except ValidationError:
                continue
            if not 1 <= pair.passage <= len(passages) or _REFERS_TO_PROMPT.search(pair.question):
                continue
            passage = passages[pair.passage - 1]
            if not contains(passage.page_content, pair.evidence):
                logger.info("dropped golden pair: evidence not in passage", extra={"source": source})
                continue
            items.append(
                GoldenItem.create(
                    source, pair.question, pair.answer, pair.evidence, chunk_location(passage), "generated"
                )
            )
        unique = {item.id: item for item in items}
        return list(unique.values())[: self.per_document]
