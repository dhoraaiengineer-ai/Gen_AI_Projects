"""Closed value sets shared by models, CHECK constraints, schemas, and the state machine."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VEHICLE_OWNER = "vehicle_owner"
    SERVICE_ADVISOR = "service_advisor"
    TECHNICIAN = "technician"
    WARRANTY_ADMIN = "warranty_admin"
    ADMIN = "admin"


STAFF_ROLES = frozenset({Role.SERVICE_ADVISOR, Role.TECHNICIAN, Role.WARRANTY_ADMIN})


class ROStatus(StrEnum):
    DRAFT = "DRAFT"
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    DIAGNOSING = "DIAGNOSING"
    INFO_PENDING = "INFO_PENDING"
    ESTIMATE_READY = "ESTIMATE_READY"
    AWAITING_OWNER_APPROVAL = "AWAITING_OWNER_APPROVAL"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    IN_REPAIR = "IN_REPAIR"
    QUALITY_CHECK = "QUALITY_CHECK"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ClaimStatus(StrEnum):
    DRAFT = "DRAFT"
    PREPARED = "PREPARED"
    WARRANTY_REVIEW_REQUIRED = "WARRANTY_REVIEW_REQUIRED"
    SUBMITTED_TO_OEM = "SUBMITTED_TO_OEM"
    OEM_ACCEPTED = "OEM_ACCEPTED"
    OEM_REJECTED = "OEM_REJECTED"
    RETURNED_FOR_INFO = "RETURNED_FOR_INFO"
    REJECTED_BY_DEALER = "REJECTED_BY_DEALER"


def values(enum: type[StrEnum]) -> tuple[str, ...]:
    return tuple(m.value for m in enum)
