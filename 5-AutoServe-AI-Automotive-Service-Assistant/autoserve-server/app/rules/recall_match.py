"""Deterministic recall / TSB matching (ADR-006). Pure functions — no DB, no LLM.

A vehicle is covered when model matches, model year is within [from, to], and the VIN serial (positions 12-17)
is within [serial_from, serial_to] inclusive. Serials are fixed-width 6-character strings, compared as integers
when numeric (else lexicographically).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class VinRange:
    model_id: uuid.UUID
    model_year_from: int
    model_year_to: int
    serial_from: str | None
    serial_to: str | None


@dataclass(frozen=True)
class VehicleKey:
    model_id: uuid.UUID
    model_year: int
    vin: str

    @property
    def serial(self) -> str:
        return self.vin[11:17]


def _key(serial: str) -> tuple[int, int | str]:
    return (0, int(serial)) if serial.isdigit() else (1, serial)


def in_range(vehicle: VehicleKey, rng: VinRange) -> bool:
    if vehicle.model_id != rng.model_id:
        return False
    if not rng.model_year_from <= vehicle.model_year <= rng.model_year_to:
        return False
    if rng.serial_from is None or rng.serial_to is None:
        return True
    return _key(rng.serial_from) <= _key(vehicle.serial) <= _key(rng.serial_to)


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [k for k in keywords if k.lower() in low]
