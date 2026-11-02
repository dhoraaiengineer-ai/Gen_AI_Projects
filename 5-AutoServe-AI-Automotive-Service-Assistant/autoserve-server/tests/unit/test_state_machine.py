"""Pure transition-table tests for both machines (rules/80: every allowed + forbidden transition)."""

from __future__ import annotations

import itertools

import pytest

from app.core.errors import ForbiddenRole, InvalidTransition, RationaleRequired
from app.models.enums import ClaimStatus, ROStatus
from app.services.state_machine import CLAIM_TERMINAL, RO_TERMINAL, TABLES, check_transition

ACTORS = ("vehicle_owner", "service_advisor", "technician", "warranty_admin", "admin", "system")
MACHINES = {"repair_order": ROStatus, "warranty_claim": ClaimStatus}

ALLOWED = [
    (machine, f, t, actor)
    for machine, table in TABLES.items()
    for (f, t), edge in table.items()
    for actor in edge.actors
]


@pytest.mark.parametrize(("machine", "frm", "to", "actor"), ALLOWED)
def test_every_allowed_edge_accepts_its_actors(machine: str, frm: str, to: str, actor: str) -> None:
    check_transition(machine, frm, to, actor, reason="because", note="owner said yes")  # type: ignore[arg-type]


@pytest.mark.parametrize(("machine", "frm", "to", "actor"), ALLOWED)
def test_other_actors_rejected_on_allowed_edges(machine: str, frm: str, to: str, actor: str) -> None:
    edge = TABLES[machine][(frm, to)]  # type: ignore[index]
    for other in set(ACTORS) - edge.actors:
        with pytest.raises(ForbiddenRole):
            check_transition(machine, frm, to, other, reason="r", note="n")  # type: ignore[arg-type]


@pytest.mark.parametrize("machine", list(MACHINES))
def test_every_edge_not_in_table_is_invalid(machine: str) -> None:
    statuses = [s.value for s in MACHINES[machine]]
    table = TABLES[machine]  # type: ignore[index]
    for frm, to in itertools.product(statuses, statuses):
        if (frm, to) not in table:
            with pytest.raises(InvalidTransition):
                check_transition(machine, frm, to, "system", reason="r", note="n")  # type: ignore[arg-type]


def test_terminal_states_have_no_outgoing_edges() -> None:
    for machine, terminal in (("repair_order", RO_TERMINAL), ("warranty_claim", CLAIM_TERMINAL)):
        assert not [k for k in TABLES[machine] if k[0] in terminal]  # type: ignore[index]


def test_every_non_terminal_ro_state_can_be_cancelled_by_advisor_with_reason() -> None:
    for s in ROStatus:
        if s in RO_TERMINAL:
            continue
        check_transition("repair_order", s, ROStatus.CANCELLED, "service_advisor", reason="customer request", note=None)
        with pytest.raises(RationaleRequired):
            check_transition("repair_order", s, ROStatus.CANCELLED, "service_advisor", reason="  ", note=None)


def test_advisor_recording_owner_decision_needs_note_but_owner_does_not() -> None:
    for to in (ROStatus.APPROVED, ROStatus.DECLINED):
        check_transition("repair_order", ROStatus.AWAITING_OWNER_APPROVAL, to, "vehicle_owner", reason=None, note=None)
        with pytest.raises(RationaleRequired):
            check_transition(
                "repair_order", ROStatus.AWAITING_OWNER_APPROVAL, to, "service_advisor", reason=None, note=None
            )


@pytest.mark.parametrize(
    "to", [ClaimStatus.SUBMITTED_TO_OEM, ClaimStatus.RETURNED_FOR_INFO, ClaimStatus.REJECTED_BY_DEALER]
)
def test_warranty_decisions_need_rationale_and_warranty_admin(to: ClaimStatus) -> None:
    frm = ClaimStatus.WARRANTY_REVIEW_REQUIRED
    with pytest.raises(RationaleRequired):
        check_transition("warranty_claim", frm, to, "warranty_admin", reason=None, note=None)
    for role in ("admin", "service_advisor", "system"):
        with pytest.raises(ForbiddenRole):
            check_transition("warranty_claim", frm, to, role, reason="r", note=None)


def test_only_system_sets_estimate_ready_and_oem_outcomes() -> None:
    assert TABLES["repair_order"][(ROStatus.DIAGNOSING, ROStatus.ESTIMATE_READY)].actors == {"system"}
    for to in (ClaimStatus.OEM_ACCEPTED, ClaimStatus.OEM_REJECTED):
        assert TABLES["warranty_claim"][(ClaimStatus.SUBMITTED_TO_OEM, to)].actors == {"system"}
