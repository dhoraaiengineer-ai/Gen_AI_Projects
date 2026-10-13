"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from src.db.models.agents import (
    A2AMessageRow,
    AgentEvent,
    AgentRun,
    Conversation,
    McpToolCall,
    Message,
    Notification,
    NotificationRead,
)
from src.db.models.knowledge import Document, DocumentChunk, KbState, SeedState
from src.db.models.ml import FraudPrediction, MlPrediction, RiskScore
from src.db.models.payments import Account, Customer, Transaction
from src.db.models.portfolio import Approval, Holding, Order, Portfolio, RiskLimit, Trade
from src.db.models.reference import Benchmark, FinancialStatement, Instrument, MarketData
from src.db.models.security import AuditLog, Permission, RolePermission, RoleRow, User
from src.db.models.tenancy import Tenant

__all__ = [
    "A2AMessageRow",
    "Account",
    "AgentEvent",
    "AgentRun",
    "Approval",
    "AuditLog",
    "Benchmark",
    "Conversation",
    "Customer",
    "Document",
    "DocumentChunk",
    "FinancialStatement",
    "FraudPrediction",
    "Holding",
    "Instrument",
    "KbState",
    "MarketData",
    "McpToolCall",
    "Message",
    "MlPrediction",
    "Notification",
    "NotificationRead",
    "Order",
    "Permission",
    "Portfolio",
    "RiskLimit",
    "RiskScore",
    "RolePermission",
    "RoleRow",
    "SeedState",
    "Tenant",
    "Trade",
    "Transaction",
    "User",
]
