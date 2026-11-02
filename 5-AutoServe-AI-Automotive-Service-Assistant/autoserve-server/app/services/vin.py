"""Deterministic VIN validation + decode (ISO 3779 / check digit at position 9). No LLM, no network.

Synthetic Veloxa layout: 1-3 WMI "VLX" · 4-8 VDS (model code from vehicle_models.vds_code) · 9 check digit ·
10 model-year code · 11 plant code · 12-17 serial.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.errors import InvalidVin

WMI = "VLX"
_ALLOWED = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")  # no I, O, Q
_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
_TRANSLIT = {
    **{str(d): d for d in range(10)},
    **dict(zip("ABCDEFGH", range(1, 9), strict=True)),
    **dict(zip("JKLMN", range(1, 6), strict=True)),
    "P": 7,
    "R": 9,
    **dict(zip("STUVWXYZ", range(2, 10), strict=True)),
}
# Position-10 year codes repeat every 30 years; the catalogue's model-year range disambiguates.
_YEAR_CODES = "ABCDEFGHJKLMNPRSTVWXY123456789"  # A=1980/2010 … 9=2009/2039


@dataclass(frozen=True)
class ModelSpec:
    name: str
    vds_code: str
    model_year_from: int
    model_year_to: int
    plant_codes: tuple[str, ...]


@dataclass(frozen=True)
class DecodedVin:
    vin: str
    wmi: str
    model: str
    model_year: int
    plant: str
    serial: str


def normalise(vin: str) -> str:
    return vin.strip().upper()


def compute_check_digit(vin: str) -> str:
    """Check digit for a 17-char VIN (position 9 is ignored in the sum: weight 0)."""
    total = sum(_TRANSLIT[c] * w for c, w in zip(vin, _WEIGHTS, strict=True))
    rem = total % 11
    return "X" if rem == 10 else str(rem)


def validate_vin(vin: str) -> str:
    """Return the normalised VIN or raise InvalidVin with a machine-readable reason."""
    v = normalise(vin)
    if len(v) != 17:
        raise InvalidVin(details={"reason": "length"})
    if not _ALLOWED.match(v):
        raise InvalidVin(details={"reason": "characters"})
    if v[8] != compute_check_digit(v):
        raise InvalidVin(details={"reason": "check_digit"})
    return v


def year_from_code(code: str, year_from: int, year_to: int) -> int | None:
    idx = _YEAR_CODES.find(code)
    if idx < 0:
        return None
    candidates = [1980 + idx + 30 * k for k in range(4)]
    matches = [y for y in candidates if year_from <= y <= year_to]
    return matches[0] if len(matches) == 1 else None


def year_code(model_year: int) -> str:
    return _YEAR_CODES[(model_year - 1980) % 30]


def decode_vin(vin: str, catalogue: Iterable[ModelSpec]) -> DecodedVin:
    """Validate + decode against the vehicle_models catalogue. Unknown WMI/VDS/year/plant → InvalidVin."""
    v = validate_vin(vin)
    if v[:3] != WMI:
        raise InvalidVin(details={"reason": "wmi"})
    spec = next((m for m in catalogue if m.vds_code == v[3:8]), None)
    if spec is None:
        raise InvalidVin(details={"reason": "unknown_model"})
    year = year_from_code(v[9], spec.model_year_from, spec.model_year_to)
    if year is None:
        raise InvalidVin(details={"reason": "model_year"})
    if v[10] not in spec.plant_codes:
        raise InvalidVin(details={"reason": "plant"})
    return DecodedVin(vin=v, wmi=v[:3], model=spec.name, model_year=year, plant=v[10], serial=v[11:])


def build_vin(vds_code: str, model_year: int, plant: str, serial: str) -> str:
    """Build a valid synthetic Veloxa VIN (seed data / tests)."""
    if len(vds_code) != 5 or len(plant) != 1 or len(serial) != 6:
        raise ValueError("vds_code=5, plant=1, serial=6 characters")
    draft = f"{WMI}{vds_code}0{year_code(model_year)}{plant}{serial}"
    return draft[:8] + compute_check_digit(draft) + draft[9:]
