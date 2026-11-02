"""Intake node: one missing field at a time, verbatim complaint, deterministic validation (specs/agents/01)."""

from __future__ import annotations

import pytest

from app.graph.nodes.intake import GarageVehicle, intake_turn, match_vehicle, parse_choice, parse_km
from app.services.llm_service import FakeLLM

ARIA = GarageVehicle("v-aria", "Aria", 2022, "100001", 30_000)
VOLT = GarageVehicle("v-volt", "Volt", 2024, "100012", 12_000)
SLOTS = ["2026-11-02T09:00:00+00:00", "2026-11-02T11:00:00+00:00", "2026-11-02T14:00:00+00:00"]


async def slots_for(vehicle_id: str) -> tuple[str, list[str]]:
    return "dealer-1", SLOTS


@pytest.mark.parametrize(
    ("text", "km"),
    [("42,000 km", 42000), ("about 42000", 42000), ("42k", 42000), ("42 000 kms", 42000), ("no idea", None)],
)
def test_parse_km(text: str, km: int | None) -> None:
    assert parse_km(text) == km


@pytest.mark.parametrize(
    ("text", "idx"), [("2", 2), ("the first one", 1), ("third please", 3), ("5", None), ("x", None)]
)
def test_parse_choice(text: str, idx: int | None) -> None:
    assert parse_choice(text, 3) == idx


def test_match_vehicle_by_model_vin_or_number() -> None:
    garage = [ARIA, VOLT]
    assert match_vehicle("my volt", garage) == VOLT
    assert match_vehicle("the one ending 100001", garage) == ARIA
    assert match_vehicle("2", garage) == VOLT
    assert match_vehicle("my car", garage) is None


async def test_full_booking_dialogue_asks_one_field_at_a_time() -> None:
    llm = FakeLLM(structured=[{"complaint_span": None, "odometer_km": None}])
    t1 = await intake_turn("I want to book a service", None, [ARIA, VOLT], slots_for, llm)
    assert t1.awaiting == "vehicle" and len(t1.options) == 2
    t2 = await intake_turn("the Volt", t1.state, [ARIA, VOLT], slots_for, None)
    assert t2.awaiting == "odometer" and t2.state["vehicle_id"] == "v-volt"
    t3 = await intake_turn("12,500 km", t2.state, [ARIA, VOLT], slots_for, None)
    assert t3.awaiting == "complaint" and t3.state["odometer_km"] == 12500
    words = "Charging stops at about 80 percent at home"
    t4 = await intake_turn(words, t3.state, [ARIA, VOLT], slots_for, None)
    assert t4.awaiting == "slot" and t4.state["complaint_text"] == words and len(t4.options) == 3
    t5 = await intake_turn("2", t4.state, [ARIA, VOLT], slots_for, None)
    assert t5.awaiting == "confirm" and t5.state["slot_start"] == SLOTS[1] and "Shall I book it" in t5.reply
    t6 = await intake_turn("yes please", t5.state, [ARIA, VOLT], slots_for, None)
    assert t6.ready_to_book and t6.state["idempotency_key"] == t1.state["idempotency_key"]


async def test_single_vehicle_is_auto_selected_and_verbatim_complaint_extracted() -> None:
    text = "Please book my car in, there is a grinding noise from the front brakes. It shows 31000 km."
    llm = FakeLLM(structured=[{"complaint_span": "grinding noise from the front brakes", "odometer_km": 31000}])
    t = await intake_turn(text, None, [ARIA], slots_for, llm)
    assert t.state["vehicle_id"] == "v-aria"
    assert t.state["complaint_text"] == "grinding noise from the front brakes"
    assert t.state["odometer_km"] == 31000 and t.awaiting == "slot"


async def test_paraphrased_complaint_from_llm_is_ignored() -> None:
    llm = FakeLLM(structured=[{"complaint_span": "Brake pads worn out", "odometer_km": None}])
    t = await intake_turn("book me in, grinding noise when braking", None, [ARIA], slots_for, llm)
    assert t.state["complaint_text"] is None and t.awaiting == "odometer"


async def test_llm_odometer_must_match_text() -> None:
    llm = FakeLLM(structured=[{"complaint_span": None, "odometer_km": 99999}])
    t = await intake_turn("book a service please", None, [ARIA], slots_for, llm)
    assert t.state["odometer_km"] is None and t.awaiting == "odometer"


async def test_odometer_lower_than_last_record_is_rejected() -> None:
    t1 = await intake_turn("book a service", None, [ARIA], slots_for, None)
    t2 = await intake_turn("25,000 km", t1.state, [ARIA], slots_for, None)
    assert t2.awaiting == "odometer" and t2.state["odometer_km"] is None
    assert "lower than the last recorded odometer (30,000 km)" in t2.reply


async def test_invalid_slot_choice_reasks() -> None:
    t = await intake_turn("book", None, [ARIA], slots_for, None)
    t = await intake_turn("31000", t.state, [ARIA], slots_for, None)
    t = await intake_turn("noise", t.state, [ARIA], slots_for, None)
    t = await intake_turn("whenever", t.state, [ARIA], slots_for, None)
    assert t.awaiting == "slot" and t.reply.startswith("Please pick one")


async def test_no_at_confirm_cancels() -> None:
    t = await intake_turn("book", None, [ARIA], slots_for, None)
    for msg in ("31000", "noise", "1"):
        t = await intake_turn(msg, t.state, [ARIA], slots_for, None)
    t = await intake_turn("no", t.state, [ARIA], slots_for, None)
    assert t.cancelled and not t.state["active"]


async def test_llm_failure_does_not_block_booking() -> None:
    t = await intake_turn("book a service", None, [ARIA], slots_for, FakeLLM())  # FakeLLM with no responses raises
    assert t.awaiting == "odometer"


async def test_empty_garage() -> None:
    t = await intake_turn("book", None, [], slots_for, None)
    assert t.cancelled


async def test_cancel_works_at_any_step() -> None:
    t = await intake_turn("book", None, [ARIA], slots_for, None)
    assert t.awaiting == "odometer"
    t = await intake_turn("cancel", t.state, [ARIA], slots_for, None)
    assert t.cancelled and not t.state["active"]
