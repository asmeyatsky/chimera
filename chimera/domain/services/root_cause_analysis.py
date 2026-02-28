"""
Root Cause Analysis Service

Architectural Intent:
- Causal AI foundation for identifying root causes of drift events
- Uses heuristic-based analysis (no ML dependencies)
- Correlates temporal and spatial signals across fleet nodes
- Produces actionable RootCauseReports with confidence scores and causal chains

Heuristic Rules:
- Multiple nodes drifting simultaneously -> likely upstream config change
- Single node drifting -> likely local issue
- Drift following a deployment -> likely deploy-related
- Confidence scored by number of corroborating signals
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum, auto
from typing import Optional

from chimera.infrastructure.agent.chimera_agent import (
    DriftReport,
    DriftSeverity,
    NodeHealth,
    AgentStatus,
)
from chimera.domain.value_objects.node import Node


class CauseCategory(Enum):
    """High-level classification of root cause."""
    LOCAL_ISSUE = auto()
    UPSTREAM_CONFIG_CHANGE = auto()
    DEPLOY_RELATED = auto()
    NETWORK_PARTITION = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class CausalFactor:
    """A single contributing factor in the causal analysis.

    Attributes:
        description: Human-readable explanation of the factor.
        weight: How strongly this factor supports the conclusion (0.0-1.0).
        evidence: Raw evidence that led to this factor being identified.
    """
    description: str
    weight: float
    evidence: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Weight must be 0.0-1.0, got {self.weight}")


@dataclass(frozen=True)
class CausalChain:
    """An ordered sequence of events forming a causal chain.

    The chain reads from root cause (first element) to observed symptom
    (last element). Each step describes how one event led to the next.

    Attributes:
        steps: Ordered descriptions from root cause to observed symptom.
        affected_node_ids: Set of node IDs involved in this chain.
    """
    steps: tuple[str, ...]
    affected_node_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def root(self) -> str:
        """The root cause (first step in the chain)."""
        return self.steps[0] if self.steps else ""

    @property
    def symptom(self) -> str:
        """The observed symptom (last step in the chain)."""
        return self.steps[-1] if self.steps else ""

    @property
    def depth(self) -> int:
        """Number of steps in the causal chain."""
        return len(self.steps)


@dataclass(frozen=True)
class RootCauseReport:
    """Complete root cause analysis report.

    Attributes:
        probable_cause: The most likely root cause category.
        confidence: Overall confidence in the analysis (0.0-1.0).
        summary: Human-readable summary of the findings.
        causal_chain: The identified chain of causation.
        contributing_factors: All factors that informed the conclusion.
        affected_node_ids: All node IDs affected by this root cause.
        analyzed_at: Timestamp of the analysis.
    """
    probable_cause: CauseCategory
    confidence: float
    summary: str
    causal_chain: CausalChain
    contributing_factors: tuple[CausalFactor, ...]
    affected_node_ids: frozenset[str]
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be 0.0-1.0, got {self.confidence}"
            )

    @property
    def is_high_confidence(self) -> bool:
        """Whether the analysis has high confidence (>= 0.7)."""
        return self.confidence >= 0.7


# ---------------------------------------------------------------------------
# Temporal / spatial correlation thresholds
# ---------------------------------------------------------------------------

#: Events within this window are considered temporally correlated.
_TEMPORAL_WINDOW = timedelta(seconds=60)

#: Minimum fraction of nodes that must drift simultaneously to classify
#: as an upstream config change (when more than one node is provided).
_UPSTREAM_THRESHOLD_RATIO = 0.5


class RootCauseAnalyzer:
    """Heuristic-based root cause analyzer for fleet drift events.

    The analyzer ingests drift reports and node health snapshots and
    produces a ``RootCauseReport`` by evaluating temporal correlations,
    spatial correlations, and deployment proximity.

    No external ML libraries are required -- all inference is rule-based.
    """

    def __init__(
        self,
        temporal_window: timedelta = _TEMPORAL_WINDOW,
        upstream_threshold_ratio: float = _UPSTREAM_THRESHOLD_RATIO,
    ) -> None:
        self._temporal_window = temporal_window
        self._upstream_threshold_ratio = upstream_threshold_ratio

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        drift_reports: list[DriftReport],
        health_snapshots: list[NodeHealth],
        deploy_timestamps: Optional[list[datetime]] = None,
        node_groups: Optional[dict[str, str]] = None,
    ) -> RootCauseReport:
        """Run root cause analysis on drift events and health data.

        Args:
            drift_reports: Drift events observed across the fleet.
            health_snapshots: Point-in-time health snapshots per node.
            deploy_timestamps: Known deployment timestamps (optional).
                Used to detect deploy-correlated drift.
            node_groups: Mapping of node_id -> group/subnet name (optional).
                Used for spatial correlation.

        Returns:
            A ``RootCauseReport`` describing the probable root cause.
        """
        if not drift_reports:
            return self._empty_report()

        factors: list[CausalFactor] = []

        # 1. Temporal correlation
        temporal_clusters = self._find_temporal_clusters(drift_reports)
        factors.extend(self._evaluate_temporal(temporal_clusters, drift_reports))

        # 2. Spatial correlation
        if node_groups:
            factors.extend(
                self._evaluate_spatial(drift_reports, node_groups)
            )

        # 3. Deploy proximity
        if deploy_timestamps:
            factors.extend(
                self._evaluate_deploy_proximity(drift_reports, deploy_timestamps)
            )

        # 4. Health signal correlation
        factors.extend(self._evaluate_health_signals(health_snapshots))

        # 5. Severity signal
        factors.extend(self._evaluate_severity(drift_reports))

        # Determine cause and build report
        cause = self._classify_cause(factors, drift_reports)
        confidence = self._compute_confidence(factors)
        chain = self._build_causal_chain(cause, drift_reports, factors)
        affected = frozenset(r.node_id for r in drift_reports)
        summary = self._generate_summary(cause, confidence, drift_reports, factors)

        return RootCauseReport(
            probable_cause=cause,
            confidence=confidence,
            summary=summary,
            causal_chain=chain,
            contributing_factors=tuple(factors),
            affected_node_ids=affected,
        )

    # ------------------------------------------------------------------
    # Temporal correlation
    # ------------------------------------------------------------------

    def _find_temporal_clusters(
        self, reports: list[DriftReport]
    ) -> list[list[DriftReport]]:
        """Group drift reports that fall within the temporal window."""
        if not reports:
            return []

        sorted_reports = sorted(reports, key=lambda r: r.detected_at)
        clusters: list[list[DriftReport]] = [[sorted_reports[0]]]

        for report in sorted_reports[1:]:
            if (
                report.detected_at - clusters[-1][-1].detected_at
                <= self._temporal_window
            ):
                clusters[-1].append(report)
            else:
                clusters.append([report])

        return clusters

    def _evaluate_temporal(
        self,
        clusters: list[list[DriftReport]],
        all_reports: list[DriftReport],
    ) -> list[CausalFactor]:
        """Produce causal factors from temporal clustering."""
        factors: list[CausalFactor] = []
        total_nodes = len({r.node_id for r in all_reports})

        for cluster in clusters:
            cluster_nodes = {r.node_id for r in cluster}
            cluster_size = len(cluster_nodes)

            if cluster_size > 1:
                ratio = cluster_size / max(total_nodes, 1)
                weight = min(ratio, 1.0)
                node_list = ", ".join(sorted(cluster_nodes))
                factors.append(
                    CausalFactor(
                        description=(
                            f"{cluster_size} nodes drifted within "
                            f"{self._temporal_window.total_seconds():.0f}s window"
                        ),
                        weight=weight,
                        evidence=f"Correlated nodes: {node_list}",
                    )
                )
            else:
                factors.append(
                    CausalFactor(
                        description="Single node drift (isolated event)",
                        weight=0.3,
                        evidence=f"Node: {cluster[0].node_id}",
                    )
                )

        return factors

    # ------------------------------------------------------------------
    # Spatial correlation
    # ------------------------------------------------------------------

    def _evaluate_spatial(
        self,
        reports: list[DriftReport],
        node_groups: dict[str, str],
    ) -> list[CausalFactor]:
        """Detect when drift concentrates in one subnet/group."""
        factors: list[CausalFactor] = []

        group_hits: dict[str, list[str]] = {}
        for report in reports:
            group = node_groups.get(report.node_id, "unknown")
            group_hits.setdefault(group, []).append(report.node_id)

        for group, node_ids in group_hits.items():
            if group == "unknown":
                continue
            if len(node_ids) > 1:
                factors.append(
                    CausalFactor(
                        description=(
                            f"Multiple drifts in group '{group}' "
                            f"({len(node_ids)} nodes)"
                        ),
                        weight=min(len(node_ids) * 0.2, 0.8),
                        evidence=f"Affected nodes: {', '.join(sorted(node_ids))}",
                    )
                )

        return factors

    # ------------------------------------------------------------------
    # Deploy proximity
    # ------------------------------------------------------------------

    def _evaluate_deploy_proximity(
        self,
        reports: list[DriftReport],
        deploy_timestamps: list[datetime],
    ) -> list[CausalFactor]:
        """Check whether drift events correlate with recent deployments."""
        factors: list[CausalFactor] = []

        for report in reports:
            for deploy_ts in deploy_timestamps:
                delta = abs(
                    (report.detected_at - deploy_ts).total_seconds()
                )
                if delta <= self._temporal_window.total_seconds():
                    # Closer to the deploy -> higher weight
                    weight = max(
                        0.3,
                        1.0 - delta / self._temporal_window.total_seconds(),
                    )
                    factors.append(
                        CausalFactor(
                            description=(
                                f"Drift on {report.node_id} detected "
                                f"{delta:.0f}s after a deployment"
                            ),
                            weight=weight,
                            evidence=(
                                f"Deploy at {deploy_ts.isoformat()}, "
                                f"drift at {report.detected_at.isoformat()}"
                            ),
                        )
                    )
                    break  # one deploy match per report is enough

        return factors

    # ------------------------------------------------------------------
    # Health signal evaluation
    # ------------------------------------------------------------------

    def _evaluate_health_signals(
        self, snapshots: list[NodeHealth]
    ) -> list[CausalFactor]:
        """Extract causal factors from health snapshot anomalies."""
        factors: list[CausalFactor] = []

        unreachable = [
            s for s in snapshots if s.status == AgentStatus.UNREACHABLE
        ]
        if unreachable:
            node_ids = ", ".join(sorted(s.node_id for s in unreachable))
            factors.append(
                CausalFactor(
                    description=(
                        f"{len(unreachable)} node(s) unreachable "
                        "(possible network partition)"
                    ),
                    weight=min(len(unreachable) * 0.25, 0.8),
                    evidence=f"Unreachable nodes: {node_ids}",
                )
            )

        degraded = [
            s for s in snapshots if s.status == AgentStatus.DEGRADED
        ]
        if degraded:
            node_ids = ", ".join(sorted(s.node_id for s in degraded))
            factors.append(
                CausalFactor(
                    description=(
                        f"{len(degraded)} node(s) in degraded state"
                    ),
                    weight=min(len(degraded) * 0.15, 0.6),
                    evidence=f"Degraded nodes: {node_ids}",
                )
            )

        return factors

    # ------------------------------------------------------------------
    # Severity evaluation
    # ------------------------------------------------------------------

    def _evaluate_severity(
        self, reports: list[DriftReport]
    ) -> list[CausalFactor]:
        """Add factors based on drift severity distribution."""
        factors: list[CausalFactor] = []

        critical_count = sum(
            1 for r in reports if r.severity == DriftSeverity.CRITICAL
        )
        if critical_count:
            factors.append(
                CausalFactor(
                    description=f"{critical_count} critical-severity drift(s) detected",
                    weight=min(critical_count * 0.2, 0.6),
                    evidence=f"Critical drifts: {critical_count}/{len(reports)}",
                )
            )

        return factors

    # ------------------------------------------------------------------
    # Cause classification
    # ------------------------------------------------------------------

    def _classify_cause(
        self,
        factors: list[CausalFactor],
        reports: list[DriftReport],
    ) -> CauseCategory:
        """Determine the most likely cause category from factors."""
        distinct_nodes = {r.node_id for r in reports}

        # Check for network partition signal
        partition_weight = sum(
            f.weight
            for f in factors
            if "unreachable" in f.description.lower()
            or "network partition" in f.description.lower()
        )
        if partition_weight >= 0.5:
            return CauseCategory.NETWORK_PARTITION

        # Check for deploy-related signal
        deploy_weight = sum(
            f.weight
            for f in factors
            if "deployment" in f.description.lower()
            or "deploy" in f.description.lower()
        )
        if deploy_weight >= 0.5:
            return CauseCategory.DEPLOY_RELATED

        # Multi-node simultaneous -> upstream
        if len(distinct_nodes) > 1:
            temporal_weight = sum(
                f.weight
                for f in factors
                if "nodes drifted within" in f.description.lower()
            )
            if temporal_weight >= self._upstream_threshold_ratio:
                return CauseCategory.UPSTREAM_CONFIG_CHANGE

        # Single node -> local
        if len(distinct_nodes) == 1:
            return CauseCategory.LOCAL_ISSUE

        # Fallback for multi-node without strong signals
        if len(distinct_nodes) > 1:
            return CauseCategory.UPSTREAM_CONFIG_CHANGE

        return CauseCategory.UNKNOWN

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _compute_confidence(self, factors: list[CausalFactor]) -> float:
        """Compute overall confidence from contributing factors.

        Confidence is the mean of factor weights, clamped to [0.0, 1.0].
        More corroborating factors increase the base, weighted by their
        individual strength.
        """
        if not factors:
            return 0.0

        total_weight = sum(f.weight for f in factors)
        avg_weight = total_weight / len(factors)

        # Bonus for having multiple corroborating signals (up to +0.15)
        corroboration_bonus = min(len(factors) * 0.03, 0.15)

        confidence = min(avg_weight + corroboration_bonus, 1.0)
        return round(confidence, 3)

    # ------------------------------------------------------------------
    # Causal chain construction
    # ------------------------------------------------------------------

    def _build_causal_chain(
        self,
        cause: CauseCategory,
        reports: list[DriftReport],
        factors: list[CausalFactor],
    ) -> CausalChain:
        """Construct a causal chain from root cause to observed symptom."""
        affected = frozenset(r.node_id for r in reports)
        node_list = ", ".join(sorted(affected))
        steps: list[str] = []

        if cause == CauseCategory.UPSTREAM_CONFIG_CHANGE:
            steps.append("Upstream configuration source changed")
            steps.append(
                f"New configuration propagated to {len(affected)} node(s)"
            )
            steps.append(
                f"Configuration drift detected on: {node_list}"
            )

        elif cause == CauseCategory.LOCAL_ISSUE:
            node_id = next(iter(affected))
            steps.append(f"Local state diverged on node {node_id}")
            steps.append("Node configuration no longer matches expected hash")
            steps.append(f"Drift detected on: {node_id}")

        elif cause == CauseCategory.DEPLOY_RELATED:
            steps.append("Deployment executed on the fleet")
            steps.append("Post-deploy state does not match expected configuration")
            steps.append(
                f"Drift detected on: {node_list}"
            )

        elif cause == CauseCategory.NETWORK_PARTITION:
            steps.append("Network connectivity disrupted")
            steps.append("Nodes became unreachable or reported stale state")
            steps.append(
                f"Drift/unreachability observed on: {node_list}"
            )

        else:
            steps.append("Root cause undetermined")
            steps.append(
                f"Drift observed on: {node_list}"
            )

        return CausalChain(
            steps=tuple(steps),
            affected_node_ids=affected,
        )

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _generate_summary(
        self,
        cause: CauseCategory,
        confidence: float,
        reports: list[DriftReport],
        factors: list[CausalFactor],
    ) -> str:
        """Generate a human-readable summary of the analysis."""
        node_count = len({r.node_id for r in reports})
        cause_label = cause.name.replace("_", " ").lower()
        pct = int(confidence * 100)

        summary = (
            f"Root cause analysis identified '{cause_label}' as the probable "
            f"cause with {pct}% confidence. "
            f"{node_count} node(s) affected, "
            f"{len(factors)} corroborating signal(s) evaluated."
        )
        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_report(self) -> RootCauseReport:
        """Return a report indicating no drift was found."""
        return RootCauseReport(
            probable_cause=CauseCategory.UNKNOWN,
            confidence=0.0,
            summary="No drift reports provided for analysis.",
            causal_chain=CausalChain(steps=("No events to analyze",)),
            contributing_factors=(),
            affected_node_ids=frozenset(),
        )
