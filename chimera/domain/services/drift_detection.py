"""
Drift Detection Service

Architectural Intent:
- Domain service for detecting configuration drift across fleet
- Determines severity and blast radius of drift
- Triggers healing workflow when drift detected

Domain Logic:
- Compares expected vs actual Nix hash
- Calculates drift severity based on hash characteristics
- Determines blast radius (what else might be affected)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Protocol, Optional
from enum import Enum, auto

from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.value_objects.congruence_report import CongruenceReport


class DriftSeverity(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class HealingAction(Enum):
    NONE = auto()
    ROLLBACK = auto()
    REBUILD = auto()
    RESTART_SERVICE = auto()


@dataclass(frozen=True)
class DriftAnalysis:
    node: Node
    expected_hash: NixHash
    actual_hash: Optional[NixHash]
    severity: DriftSeverity
    healing_action: HealingAction
    blast_radius: list[Node] = field(default_factory=list)
    recommended_fix: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def needs_healing(self) -> bool:
        return self.healing_action != HealingAction.NONE

    @property
    def is_critical(self) -> bool:
        return self.severity == DriftSeverity.CRITICAL


class DriftDetector(Protocol):
    """Port for drift detection implementations."""

    async def check_node(self, node: Node, expected_hash: NixHash) -> CongruenceReport:
        """Check a single node for drift."""
        ...

    async def get_actual_hash(self, node: Node) -> Optional[NixHash]:
        """Get the actual configuration hash from a node."""
        ...


class DriftDetectionService:
    """
    Domain service for comprehensive drift detection and analysis.

    Determines not just IF there's drift, but:
    - How severe is it?
    - What action should be taken?
    - What's the blast radius?
    """

    def __init__(self, drift_detector: DriftDetector):
        self._detector = drift_detector

    async def analyze(
        self,
        node: Node,
        expected_hash: NixHash,
    ) -> DriftAnalysis:
        """
        Perform comprehensive drift analysis on a node.
        """
        report = await self._detector.check_node(node, expected_hash)

        if report.is_congruent:
            return DriftAnalysis(
                node=node,
                expected_hash=expected_hash,
                actual_hash=expected_hash,
                severity=DriftSeverity.LOW,
                healing_action=HealingAction.NONE,
                recommended_fix="No action needed - system is congruent.",
            )

        actual = report.actual_hash
        severity = self._calculate_severity(expected_hash, actual)
        healing_action = self._determine_healing_action(severity, actual)
        recommended_fix = self._generate_fix_recommendation(healing_action, node)

        return DriftAnalysis(
            node=node,
            expected_hash=expected_hash,
            actual_hash=actual,
            severity=severity,
            healing_action=healing_action,
            recommended_fix=recommended_fix,
            blast_radius=self._calculate_blast_radius(node, []),
        )

    def _calculate_severity(
        self,
        expected: NixHash,
        actual: Optional[NixHash],
    ) -> DriftSeverity:
        """
        Calculate drift severity based on hash analysis.

        Severity rules:
        - Unknown hash (None): CRITICAL
        - All zeros / placeholder: HIGH
        - Different hash: MEDIUM to HIGH depending on delta
        """
        if actual is None:
            return DriftSeverity.CRITICAL

        actual_str = str(actual)

        if actual_str in ("", "0" * 32, "00000000000000000000000000000000"):
            return DriftSeverity.HIGH

        if actual_str == expected:
            return DriftSeverity.LOW

        return DriftSeverity.MEDIUM

    def _determine_healing_action(
        self,
        severity: DriftSeverity,
        actual_hash: Optional[NixHash],
    ) -> HealingAction:
        """
        Determine appropriate healing action based on severity.
        """
        if severity == DriftSeverity.CRITICAL:
            return HealingAction.ROLLBACK

        if severity == DriftSeverity.HIGH:
            return HealingAction.REBUILD

        if severity == DriftSeverity.MEDIUM:
            return HealingAction.RESTART_SERVICE

        return HealingAction.NONE

    def _calculate_blast_radius(
        self,
        node: Node,
        all_nodes: list[Node],
    ) -> list[Node]:
        """Calculate blast radius using host-prefix grouping.

        Nodes sharing the same hostname prefix (up to the first dot or
        the first digit-run) are considered in the same blast radius group.
        """
        def _prefix(n: Node) -> str:
            host = n.host
            # Group by first label of hostname
            if "." in host:
                return host.split(".")[0].rstrip("0123456789-")
            return host.rstrip("0123456789-")

        node_prefix = _prefix(node)
        affected = [
            n for n in all_nodes
            if n != node and _prefix(n) == node_prefix
        ]
        return affected

    def _generate_fix_recommendation(
        self,
        action: HealingAction,
        node: Node,
    ) -> str:
        """Generate human-readable fix recommendation."""
        if action == HealingAction.NONE:
            return "No fix required."

        if action == HealingAction.ROLLBACK:
            return (
                f"Rollback node {node.host} to previous generation. "
                "Critical drift detected - immediate rollback recommended."
            )

        if action == HealingAction.REBUILD:
            return (
                f"Rebuild node {node.host} with expected configuration. "
                "Significant drift detected - full rebuild required."
            )

        if action == HealingAction.RESTART_SERVICE:
            return (
                f"Restart affected services on {node.host}. "
                "Minor drift detected - service restart should resolve."
            )

        return "Manual intervention required."

    async def _analyze_with_fleet(
        self,
        node: Node,
        expected_hash: NixHash,
        all_nodes: list[Node],
    ) -> DriftAnalysis:
        """Analyze a node with fleet context for blast radius."""
        report = await self._detector.check_node(node, expected_hash)

        if report.is_congruent:
            return DriftAnalysis(
                node=node,
                expected_hash=expected_hash,
                actual_hash=expected_hash,
                severity=DriftSeverity.LOW,
                healing_action=HealingAction.NONE,
                recommended_fix="No action needed - system is congruent.",
            )

        actual = report.actual_hash
        severity = self._calculate_severity(expected_hash, actual)
        healing_action = self._determine_healing_action(severity, actual)
        recommended_fix = self._generate_fix_recommendation(healing_action, node)

        return DriftAnalysis(
            node=node,
            expected_hash=expected_hash,
            actual_hash=actual,
            severity=severity,
            healing_action=healing_action,
            recommended_fix=recommended_fix,
            blast_radius=self._calculate_blast_radius(node, all_nodes),
        )

    async def analyze_fleet(
        self,
        nodes: list[Node],
        expected_hash: NixHash,
    ) -> list[DriftAnalysis]:
        """
        Analyze all nodes in the fleet for drift.

        Returns analysis for all nodes, sorted by severity (critical first).
        """
        import asyncio

        analyses = await asyncio.gather(
            *[self._analyze_with_fleet(node, expected_hash, nodes) for node in nodes]
        )

        return sorted(
            analyses,
            key=lambda a: (
                0 if a.severity == DriftSeverity.CRITICAL else 1,
                0 if a.severity == DriftSeverity.HIGH else 1,
                0 if a.severity == DriftSeverity.MEDIUM else 1,
                1,
            ),
        )

    def get_healing_plan(
        self,
        analyses: list[DriftAnalysis],
    ) -> dict[HealingAction, list[DriftAnalysis]]:
        """
        Group analyses by recommended healing action.
        """
        plan: dict[HealingAction, list[DriftAnalysis]] = {
            HealingAction.ROLLBACK: [],
            HealingAction.REBUILD: [],
            HealingAction.RESTART_SERVICE: [],
            HealingAction.NONE: [],
        }

        for analysis in analyses:
            plan[analysis.healing_action].append(analysis)

        return plan
