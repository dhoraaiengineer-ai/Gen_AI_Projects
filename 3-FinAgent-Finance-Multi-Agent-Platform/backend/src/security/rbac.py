"""Roles and permissions.

Code holds the defaults (``DEFAULT_ROLE_PERMISSIONS``); the seed copies them into the ``roles``,
``permissions`` and ``role_permissions`` tables, where an admin can change them. FastAPI
dependencies (``require_user``, ``require_role``) are added with the API in Stage 8.
"""

from __future__ import annotations

from src.core.domain import Role

ROLE_DESCRIPTIONS: dict[Role, tuple[int, str]] = {
    Role.ADMIN: (100, "Platform administration; full access, approvals off by default"),
    Role.COMPLIANCE_OFFICER: (80, "Compliance validation, approvals, audit log, documents"),
    Role.RISK_MANAGER: (70, "Risk analytics, stress tests, rebalance proposals"),
    Role.PORTFOLIO_MANAGER: (70, "Portfolio analytics, rebalance proposals, approvals"),
    Role.FRAUD_ANALYST: (50, "Fraud analytics and transaction investigation (PII masked)"),
    Role.ANALYST: (40, "Research, market and portfolio analysis; runs agents"),
    Role.VIEWER: (10, "Read-only dashboards"),
}

PERMISSIONS: dict[str, str] = {
    "dashboard:read": "View dashboards, portfolios and market data",
    "agents:run": "Ask the assistant and run agents",
    "risk:analyze": "Run risk tools (VaR, stress tests, risk scores)",
    "fraud:analyze": "Run fraud tools and view payment transactions",
    "customers:read": "View customer profiles (PII masked)",
    "portfolio:propose": "Propose rebalances (draft orders only)",
    "approvals:decide": "Approve or reject pending approvals",
    "documents:write": "Upload and delete knowledge-base documents",
    "documents:read_restricted": "Read restricted and confidential documents",
    "audit:read": "Read the audit log",
    "admin:manage": "Manage users, roles and settings",
}

_ALL = frozenset(PERMISSIONS)
_BASE = frozenset({"dashboard:read", "agents:run"})

DEFAULT_ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    # Segregation of duties: admin does not approve by default.
    Role.ADMIN: _ALL - {"approvals:decide"},
    Role.COMPLIANCE_OFFICER: _BASE
    | {
        "risk:analyze",
        "fraud:analyze",
        "customers:read",
        "approvals:decide",
        "documents:write",
        "documents:read_restricted",
        "audit:read",
    },
    Role.RISK_MANAGER: _BASE | {"risk:analyze", "portfolio:propose", "documents:read_restricted"},
    Role.PORTFOLIO_MANAGER: _BASE
    | {"risk:analyze", "portfolio:propose", "approvals:decide", "documents:read_restricted"},
    Role.FRAUD_ANALYST: _BASE | {"fraud:analyze", "customers:read"},
    Role.ANALYST: _BASE | {"risk:analyze", "documents:write"},
    Role.VIEWER: frozenset({"dashboard:read"}),
}

APPROVER_ROLES = frozenset({Role.PORTFOLIO_MANAGER, Role.COMPLIANCE_OFFICER})

# Document classifications each role may read (mandatory RAG filter).
CLASSIFICATION_ACCESS: dict[Role, frozenset[str]] = {
    role: frozenset({"public", "internal"})
    | (
        frozenset({"restricted", "confidential"})
        if "documents:read_restricted" in perms
        else frozenset()
    )
    for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
}


def has_permission(role: Role | str, permission: str) -> bool:
    try:
        return permission in DEFAULT_ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False


def role_rank(role: Role | str) -> int:
    try:
        return ROLE_DESCRIPTIONS[Role(role)][0]
    except ValueError:
        return 0
