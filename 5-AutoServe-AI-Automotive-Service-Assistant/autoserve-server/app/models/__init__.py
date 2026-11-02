"""ORM models — importing this package registers every table on Base.metadata (Alembic autogenerate)."""

from app.models.base import Base
from app.models.comms import Conversation, Message, Notification
from app.models.documents import ChecklistItem, Document, ExtractedField
from app.models.identity import Dealer, RoleRow, User
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.platform import AuditLog, ConfigVersion, GraphNodeRun, IdempotencyKey, LlmUsage
from app.models.pricing import EstimateLine, LabourOp, Part
from app.models.vehicles import MaintenanceAlert, Recall, RecallVinRange, ServiceHistory, Tsb, Vehicle, VehicleModel
from app.models.warranty import ReviewDecision, RiskFlag, WarrantyClaim, WarrantyFinding, WarrantyStatusHistory
from app.models.workshop import (
    Appointment,
    DealerCapacity,
    DiagnosticFinding,
    RepairOrder,
    ROComplaint,
    ROStatusHistory,
)

__all__ = [
    "Appointment",
    "AuditLog",
    "Base",
    "ChecklistItem",
    "ConfigVersion",
    "Conversation",
    "Dealer",
    "DealerCapacity",
    "DiagnosticFinding",
    "Document",
    "EstimateLine",
    "ExtractedField",
    "GraphNodeRun",
    "IdempotencyKey",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "LabourOp",
    "LlmUsage",
    "MaintenanceAlert",
    "Message",
    "Notification",
    "Part",
    "ROComplaint",
    "ROStatusHistory",
    "Recall",
    "RecallVinRange",
    "RepairOrder",
    "ReviewDecision",
    "RiskFlag",
    "RoleRow",
    "ServiceHistory",
    "Tsb",
    "User",
    "Vehicle",
    "VehicleModel",
    "WarrantyClaim",
    "WarrantyFinding",
    "WarrantyStatusHistory",
]
