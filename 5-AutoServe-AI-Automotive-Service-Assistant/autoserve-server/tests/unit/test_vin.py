from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.errors import InvalidVin
from app.services.vin import (
    ModelSpec,
    build_vin,
    compute_check_digit,
    decode_vin,
    validate_vin,
    year_code,
    year_from_code,
)

CATALOGUE = (
    ModelSpec("Aria", "AR1P0", 2021, 2026, ("K", "M")),
    ModelSpec("Volt", "VT3E0", 2023, 2026, ("M",)),
)

# Public ISO 3779 worked example (check digit 'X' case) — exercises the algorithm, not domain data.
KNOWN_VALID_X = "1M8GDM9AXKP042788"


def test_known_reference_vin_with_x_check_digit() -> None:
    assert compute_check_digit(KNOWN_VALID_X) == "X"
    assert validate_vin(KNOWN_VALID_X) == KNOWN_VALID_X


def test_build_then_decode_roundtrip() -> None:
    vin = build_vin("AR1P0", 2024, "K", "100042")
    decoded = decode_vin(vin, CATALOGUE)
    assert (decoded.model, decoded.model_year, decoded.plant, decoded.serial) == ("Aria", 2024, "K", "100042")
    assert decoded.wmi == "VLX"


def test_lowercase_and_spaces_are_normalised() -> None:
    vin = build_vin("AR1P0", 2022, "M", "000007")
    assert validate_vin(f"  {vin.lower()} ") == vin


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda v: v[:16], "length"),
        (lambda v: v + "1", "length"),
        (lambda v: v[:12] + "I" + v[13:], "characters"),
        (lambda v: v[:12] + "O" + v[13:], "characters"),
        (lambda v: v[:12] + "Q" + v[13:], "characters"),
        (lambda v: v[:12] + "-" + v[13:], "characters"),
    ],
)
def test_invalid_format(mutate, reason: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InvalidVin) as exc:
        validate_vin(mutate(build_vin("AR1P0", 2024, "K", "100042")))
    assert exc.value.details == {"reason": reason}


def test_wrong_check_digit_rejected() -> None:
    vin = build_vin("AR1P0", 2024, "K", "100042")
    wrong = "0" if vin[8] != "0" else "1"
    with pytest.raises(InvalidVin) as exc:
        validate_vin(vin[:8] + wrong + vin[9:])
    assert exc.value.details == {"reason": "check_digit"}


def test_foreign_wmi_rejected_on_decode() -> None:
    with pytest.raises(InvalidVin) as exc:
        decode_vin(KNOWN_VALID_X, CATALOGUE)
    assert exc.value.details == {"reason": "wmi"}


def test_unknown_model_code_rejected() -> None:
    with pytest.raises(InvalidVin) as exc:
        decode_vin(build_vin("ZZ9Z9", 2024, "K", "100042"), CATALOGUE)
    assert exc.value.details == {"reason": "unknown_model"}


def test_model_year_outside_catalogue_range_rejected() -> None:
    with pytest.raises(InvalidVin) as exc:
        decode_vin(build_vin("VT3E0", 2021, "M", "100042"), CATALOGUE)  # Volt starts 2023
    assert exc.value.details == {"reason": "model_year"}


def test_plant_not_in_catalogue_rejected() -> None:
    with pytest.raises(InvalidVin) as exc:
        decode_vin(build_vin("VT3E0", 2024, "K", "100042"), CATALOGUE)  # Volt built at M only
    assert exc.value.details == {"reason": "plant"}


@pytest.mark.parametrize("year", [2010, 2020, 2024, 2026, 2030])
def test_year_code_roundtrip(year: int) -> None:
    assert year_from_code(year_code(year), year - 1, year + 1) == year


def test_year_code_invalid_character() -> None:
    assert year_from_code("U", 2000, 2040) is None  # U is not a year code


_SERIAL = st.text(alphabet="0123456789ABCDEFGHJKLMNPRSTUVWXYZ", min_size=6, max_size=6)


@given(year=st.integers(2021, 2026), plant=st.sampled_from(["K", "M"]), serial=_SERIAL)
def test_property_built_vins_always_valid_and_decode(year: int, plant: str, serial: str) -> None:
    vin = build_vin("AR1P0", year, plant, serial)
    assert validate_vin(vin) == vin
    assert decode_vin(vin, CATALOGUE).model_year == year


@given(year=st.integers(2021, 2026), serial=_SERIAL, pos=st.integers(11, 16), repl=st.sampled_from("0123456789"))
def test_property_single_digit_change_breaks_check_digit_or_keeps_it_consistent(
    year: int, serial: str, pos: int, repl: str
) -> None:
    vin = build_vin("AR1P0", year, "K", serial)
    mutated = vin[:pos] + repl + vin[pos + 1 :]
    expected_valid = compute_check_digit(mutated) == mutated[8]
    try:
        validate_vin(mutated)
        assert expected_valid
    except InvalidVin:
        assert not expected_valid
