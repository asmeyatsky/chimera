"""
Policy Engine with RBAC

Architectural Intent:
- Defines authorization for healing operations
- Permission enum covers all healing-related actions
- Role entity groups permissions for RBAC
- PolicyDecision value object captures authorization results

Design Decisions:
- Permissions are granular (per-action)
- Roles are composable (a role has a set of permissions)
- Evaluation is deterministic: explicit deny > allow > default deny
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Permission(Enum):
    DEPLOY = auto()
    ROLLBACK = auto()
    HEAL_RESTART = auto()
    HEAL_REBUILD = auto()
    HEAL_ROLLBACK = auto()
    VIEW_STATUS = auto()
    MANAGE_NODES = auto()
    MANAGE_SLOS = auto()
    ADMIN = auto()


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a policy evaluation."""

    allowed: bool
    reason: str
    permission: Permission
    principal: str = ""

    @staticmethod
    def allow(permission: Permission, principal: str, reason: str = "") -> PolicyDecision:
        return PolicyDecision(
            allowed=True,
            reason=reason or f"{principal} has {permission.name}",
            permission=permission,
            principal=principal,
        )

    @staticmethod
    def deny(permission: Permission, principal: str, reason: str = "") -> PolicyDecision:
        return PolicyDecision(
            allowed=False,
            reason=reason or f"{principal} lacks {permission.name}",
            permission=permission,
            principal=principal,
        )


@dataclass
class Role:
    """RBAC role with a set of permissions."""

    name: str
    permissions: set[Permission] = field(default_factory=set)
    description: str = ""

    def has_permission(self, permission: Permission) -> bool:
        if Permission.ADMIN in self.permissions:
            return True
        return permission in self.permissions

    def grant(self, permission: Permission) -> None:
        self.permissions.add(permission)

    def revoke(self, permission: Permission) -> None:
        self.permissions.discard(permission)


# Predefined roles
VIEWER_ROLE = Role(
    name="viewer",
    permissions={Permission.VIEW_STATUS},
    description="Read-only access to fleet status",
)

OPERATOR_ROLE = Role(
    name="operator",
    permissions={
        Permission.VIEW_STATUS,
        Permission.DEPLOY,
        Permission.ROLLBACK,
        Permission.HEAL_RESTART,
    },
    description="Can deploy and perform basic healing",
)

ADMIN_ROLE = Role(
    name="admin",
    permissions={Permission.ADMIN},
    description="Full administrative access",
)


class PolicyEngine:
    """Evaluates authorization decisions."""

    def __init__(self) -> None:
        self._principal_roles: dict[str, list[Role]] = {}

    def assign_role(self, principal: str, role: Role) -> None:
        if principal not in self._principal_roles:
            self._principal_roles[principal] = []
        self._principal_roles[principal].append(role)

    def evaluate(self, principal: str, permission: Permission) -> PolicyDecision:
        roles = self._principal_roles.get(principal, [])
        if not roles:
            return PolicyDecision.deny(
                permission, principal, f"No roles assigned to {principal}"
            )

        for role in roles:
            if role.has_permission(permission):
                return PolicyDecision.allow(
                    permission, principal, f"Granted via role '{role.name}'"
                )

        return PolicyDecision.deny(
            permission,
            principal,
            f"None of {principal}'s roles grant {permission.name}",
        )
