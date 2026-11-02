"""ServiceGraphState (specs/graph-state.md). Every node returns a partial dict with ONLY the fields it owns.

Values are JSON-serialisable dicts (Pydantic `model_dump(mode="json")`) so the Postgres checkpointer can store them.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class ServiceGraphState(TypedDict, total=False):
    # identity / context — set by the API layer when a thread starts (read-only for nodes)
    thread_id: str
    ro_id: str
    claim_id: str | None
    dealer_id: str | None
    actor: dict[str, Any]
    request_id: str
    entrypoint: Literal["warranty", "claim_review", "resume"]

    intake: dict[str, Any]  # 1 Intake (RO load)
    vehicle_context: dict[str, Any]  # 2 Vehicle Context
    documents: dict[str, Any]  # 3 Document
    diagnosis: dict[str, Any]  # 4 Diagnosis (technician-confirmed finding)
    warranty: dict[str, Any]  # 5 Warranty
    estimate: dict[str, Any]  # 6 Estimate
    risk: dict[str, Any]  # 7 Risk
    route: dict[str, Any]  # routing.py
    review: dict[str, Any]  # 9 Human Review (+ record_decision)
    notified: list[str]  # notify

    # shared reducers
    safety_critical: Annotated[bool, operator.or_]
    execution_trace: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
