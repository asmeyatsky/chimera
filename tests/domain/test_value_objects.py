"""Tests for value objects: NixHash, SessionId, CongruenceReport."""

import pytest
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.congruence_report import CongruenceReport
from chimera.domain.value_objects.node import Node


class TestNixHash:
    def test_valid_hash(self):
        h = NixHash("00000000000000000000000000000000")
        assert str(h) == "00000000000000000000000000000000"

    def test_valid_base32_hash(self):
        h = NixHash("abcdefghijklmnop0123456789abcdef")
        assert h.value == "abcdefghijklmnop0123456789abcdef"

    def test_invalid_too_short(self):
        with pytest.raises(ValueError, match="Invalid Nix hash"):
            NixHash("abc")

    def test_invalid_uppercase(self):
        with pytest.raises(ValueError, match="Invalid Nix hash"):
            NixHash("ABCDEFGHIJKLMNOP0123456789ABCDEF")

    def test_frozen(self):
        h = NixHash("00000000000000000000000000000000")
        with pytest.raises(AttributeError):
            h.value = "other"

    def test_equality(self):
        a = NixHash("00000000000000000000000000000000")
        b = NixHash("00000000000000000000000000000000")
        assert a == b


class TestSessionId:
    def test_valid_session_id(self):
        s = SessionId("my-session")
        assert str(s) == "my-session"

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            SessionId("")

    def test_frozen(self):
        s = SessionId("test")
        with pytest.raises(AttributeError):
            s.value = "other"


class TestCongruenceReport:
    def test_congruent(self):
        node = Node(host="example.com")
        h = NixHash("00000000000000000000000000000000")
        report = CongruenceReport.congruent(node, h)
        assert report.is_congruent
        assert report.expected_hash == h
        assert report.actual_hash == h

    def test_drift(self):
        node = Node(host="example.com")
        expected = NixHash("00000000000000000000000000000000")
        actual = NixHash("11111111111111111111111111111111")
        report = CongruenceReport.drift(node, expected, actual, "mismatch")
        assert not report.is_congruent
        assert report.details == "mismatch"

    def test_drift_with_none_actual(self):
        node = Node(host="example.com")
        expected = NixHash("00000000000000000000000000000000")
        report = CongruenceReport.drift(node, expected, None, "unreachable")
        assert not report.is_congruent
        assert report.actual_hash is None
