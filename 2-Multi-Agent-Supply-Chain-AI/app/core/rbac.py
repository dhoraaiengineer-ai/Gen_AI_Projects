"""Roles and role ordering. Roles come only from the JWT's `app_metadata.app_role`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    APPROVER = "approver"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return _RANK[self]

    def at_least(self, other: Role) -> bool:
        return self.rank >= other.rank

    @classmethod
    def parse(cls, value: object) -> Role:
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.VIEWER  # unknown or missing roles get the least privilege


_RANK = {Role.VIEWER: 0, Role.ANALYST: 1, Role.APPROVER: 2, Role.ADMIN: 3}


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    role: Role

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.replace(".", " ").split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or self.email[:2].upper()


SYSTEM_USER = User(id="system", email="system@supplyai.local", name="System", role=Role.ADMIN)
