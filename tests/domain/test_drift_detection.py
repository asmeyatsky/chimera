"""Tests for DriftDetectionService."""

import pytest
from unittest.mock import AsyncMock
from chimera.domain.services.drift_detection import (
    DriftDetectionService,
    DriftSeverity,
    HealingAction,
)
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.value_objects.congruence_report import CongruenceReport


def make_detector(congruent: bool, actual_hash=None):
    detector = AsyncMock()
    node = Node(host="example.com")
    expected = NixHash("00000000000000000000000000000000")

    if congruent:
        report = CongruenceReport.congruent(node, expected)
    else:
        report = CongruenceReport.drift(node, expected, actual_hash, "drift")

    detector.check_node = AsyncMock(return_value=report)
    return detector


class TestDriftDetectionService:
    @pytest.mark.asyncio
    async def test_congruent_node(self):
        detector = make_detector(congruent=True)
        service = DriftDetectionService(detector)
        node = Node(host="example.com")
        expected = NixHash("00000000000000000000000000000000")

        analysis = await service.analyze(node, expected)

        assert analysis.severity == DriftSeverity.LOW
        assert analysis.healing_action == HealingAction.NONE
        assert not analysis.needs_healing

    @pytest.mark.asyncio
    async def test_critical_drift_no_hash(self):
        detector = make_detector(congruent=False, actual_hash=None)
        service = DriftDetectionService(detector)
        node = Node(host="example.com")
        expected = NixHash("00000000000000000000000000000000")

        analysis = await service.analyze(node, expected)

        assert analysis.severity == DriftSeverity.CRITICAL
        assert analysis.healing_action == HealingAction.ROLLBACK
        assert analysis.is_critical

    @pytest.mark.asyncio
    async def test_high_drift_zero_hash(self):
        actual = NixHash("00000000000000000000000000000000")
        detector = make_detector(congruent=False, actual_hash=actual)

        # Override expected to be different
        service = DriftDetectionService(detector)
        node = Node(host="example.com")
        expected = NixHash("11111111111111111111111111111111")

        analysis = await service.analyze(node, expected)

        assert analysis.severity == DriftSeverity.HIGH
        assert analysis.healing_action == HealingAction.REBUILD

    @pytest.mark.asyncio
    async def test_medium_drift(self):
        actual = NixHash("22222222222222222222222222222222")
        detector = make_detector(congruent=False, actual_hash=actual)
        service = DriftDetectionService(detector)
        node = Node(host="example.com")
        expected = NixHash("11111111111111111111111111111111")

        analysis = await service.analyze(node, expected)

        assert analysis.severity == DriftSeverity.MEDIUM
        assert analysis.healing_action == HealingAction.RESTART_SERVICE

    @pytest.mark.asyncio
    async def test_fleet_analysis_sorted_by_severity(self):
        detector = AsyncMock()
        nodes = [
            Node(host="10.0.0.1"),
            Node(host="10.0.0.2"),
            Node(host="10.0.0.3"),
        ]
        expected = NixHash("11111111111111111111111111111111")

        # Node 1: congruent, Node 2: critical, Node 3: medium
        detector.check_node = AsyncMock(
            side_effect=[
                CongruenceReport.congruent(nodes[0], expected),
                CongruenceReport.drift(nodes[1], expected, None, "critical"),
                CongruenceReport.drift(
                    nodes[2],
                    expected,
                    NixHash("22222222222222222222222222222222"),
                    "medium",
                ),
            ]
        )

        service = DriftDetectionService(detector)
        analyses = await service.analyze_fleet(nodes, expected)

        assert len(analyses) == 3
        assert analyses[0].severity == DriftSeverity.CRITICAL
        assert analyses[1].severity == DriftSeverity.MEDIUM
        assert analyses[2].severity == DriftSeverity.LOW

    def test_healing_plan(self):
        from chimera.domain.services.drift_detection import DriftAnalysis

        node = Node(host="example.com")
        expected = NixHash("11111111111111111111111111111111")

        analyses = [
            DriftAnalysis(
                node=node,
                expected_hash=expected,
                actual_hash=None,
                severity=DriftSeverity.CRITICAL,
                healing_action=HealingAction.ROLLBACK,
            ),
            DriftAnalysis(
                node=node,
                expected_hash=expected,
                actual_hash=expected,
                severity=DriftSeverity.LOW,
                healing_action=HealingAction.NONE,
            ),
        ]

        service = DriftDetectionService(AsyncMock())
        plan = service.get_healing_plan(analyses)

        assert len(plan[HealingAction.ROLLBACK]) == 1
        assert len(plan[HealingAction.NONE]) == 1
        assert len(plan[HealingAction.REBUILD]) == 0
