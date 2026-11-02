"""Open-recall lookup for a vehicle (deterministic VIN-range match + cited notice)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeChunk, Recall, RecallVinRange, Vehicle
from app.rules.recall_match import VehicleKey, VinRange, in_range


@dataclass(frozen=True)
class OpenRecall:
    campaign_code: str
    title: str
    component_group: str
    notice_chunk_id: str | None
    notice_source_file: str | None
    notice_page: int | None
    notice_section_id: str | None
    notice_quote: str | None
    remedy_op_code: str | None = None
    part_numbers: tuple[str, ...] = ()


def _what_to_do(content: str) -> str | None:
    for line in content.replace("\n", " ").split("What owners should do:")[1:2]:
        return line.split("Remedy:")[0].strip()
    return None


async def open_recalls_for(session: AsyncSession, vehicle: Vehicle) -> list[OpenRecall]:
    """Caller must have loaded `vehicle` through an actor-scoped repository."""
    rows = (
        await session.execute(
            select(Recall, RecallVinRange)
            .join(RecallVinRange, RecallVinRange.recall_id == Recall.id)
            .where(Recall.status == "open", RecallVinRange.model_id == vehicle.model_id)
        )
    ).all()
    key = VehicleKey(model_id=vehicle.model_id, model_year=vehicle.model_year, vin=vehicle.vin)
    out: list[OpenRecall] = []
    for recall, rng in rows:
        if not in_range(key, VinRange(rng.model_id, rng.model_year_from, rng.model_year_to, rng.vin_serial_from,
                                      rng.vin_serial_to)):  # fmt: skip
            continue
        chunk = None
        if recall.source_chunk_id and not recall.source_chunk_id.startswith("pending:"):
            chunk = await session.get(KnowledgeChunk, recall.source_chunk_id)
        md = chunk.chunk_metadata if chunk else {}
        out.append(
            OpenRecall(
                campaign_code=recall.campaign_code,
                title=recall.title,
                component_group=recall.component_group,
                notice_chunk_id=str(chunk.id) if chunk else None,
                notice_source_file=md.get("source_file"),
                notice_page=md.get("page"),
                notice_section_id=md.get("section_id"),
                notice_quote=_what_to_do(chunk.content) if chunk else None,
                remedy_op_code=recall.remedy_op_code,
                part_numbers=tuple(recall.part_numbers or ()),
            )
        )
    return out
