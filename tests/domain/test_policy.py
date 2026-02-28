"""Tests for Policy engine."""

import pytest
from chimera.domain.entities.policy import (
    Permission,
    Role,
    PolicyDecision,
    PolicyEngine,
    VIEWER_ROLE,
    OPERATOR_ROLE,
    ADMIN_ROLE,
)


class TestRole:
    def test_basic_permission(self):
        role = Role(name="test", permissions={Permission.DEPLOY})
        assert role.has_permission(Permission.DEPLOY)
        assert not role.has_permission(Permission.ROLLBACK)

    def test_admin_has_all(self):
        assert ADMIN_ROLE.has_permission(Permission.DEPLOY)
        assert ADMIN_ROLE.has_permission(Permission.ROLLBACK)
        assert ADMIN_ROLE.has_permission(Permission.MANAGE_NODES)

    def test_grant_revoke(self):
        role = Role(name="test")
        assert not role.has_permission(Permission.DEPLOY)
        role.grant(Permission.DEPLOY)
        assert role.has_permission(Permission.DEPLOY)
        role.revoke(Permission.DEPLOY)
        assert not role.has_permission(Permission.DEPLOY)


class TestPolicyDecision:
    def test_allow(self):
        d = PolicyDecision.allow(Permission.DEPLOY, "alice")
        assert d.allowed
        assert d.principal == "alice"

    def test_deny(self):
        d = PolicyDecision.deny(Permission.DEPLOY, "bob")
        assert not d.allowed


class TestPolicyEngine:
    def test_no_roles_denied(self):
        engine = PolicyEngine()
        decision = engine.evaluate("alice", Permission.DEPLOY)
        assert not decision.allowed

    def test_viewer_can_view(self):
        engine = PolicyEngine()
        engine.assign_role("alice", VIEWER_ROLE)
        decision = engine.evaluate("alice", Permission.VIEW_STATUS)
        assert decision.allowed

    def test_viewer_cannot_deploy(self):
        engine = PolicyEngine()
        engine.assign_role("alice", VIEWER_ROLE)
        decision = engine.evaluate("alice", Permission.DEPLOY)
        assert not decision.allowed

    def test_operator_can_deploy(self):
        engine = PolicyEngine()
        engine.assign_role("bob", OPERATOR_ROLE)
        decision = engine.evaluate("bob", Permission.DEPLOY)
        assert decision.allowed

    def test_admin_can_do_anything(self):
        engine = PolicyEngine()
        engine.assign_role("admin", ADMIN_ROLE)
        for perm in Permission:
            assert engine.evaluate("admin", perm).allowed
