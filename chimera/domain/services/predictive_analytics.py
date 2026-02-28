"""
Predictive Analytics Service

Architectural Intent:
- Heuristic-based risk scoring for fleet nodes
- Records drift history and produces risk predictions
- Foundation for ML-based predictions in the future

Design Decisions:
- RiskScore is a frozen value object
- PredictiveAnalyticsService maintains drift history in-memory
- Risk scoring uses weighted heuristics (frequency, recency, severity)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum, auto
from typing import Optional
from chimera.domain.value_objects.node import Node
from chimera.domain.services.drift_detection import DriftSeverity


class RiskLevel(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass(frozen=True)
class RiskScore:
    """Value object representing a risk assessment for a node."""

    node: Node
    score: float  # 0.0 to 1.0
    level: RiskLevel
    factors: dict[str, float] = field(default_factory=dict)
    predicted_drift_probability: float = 0.0
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_high_risk(self) -> bool:
        return self.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


@dataclass
class DriftHistoryEntry:
    """Record of a drift event."""

    node: Node
    severity: DriftSeverity
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved: bool = False
    resolution_time_seconds: Optional[float] = None


class PredictiveAnalyticsService:
    """Heuristic-based risk scoring and drift prediction."""

    def __init__(self, history_window_hours: int = 168):  # 7 days
        self._history: list[DriftHistoryEntry] = []
        self._window_hours = history_window_hours

    def record_drift(
        self,
        node: Node,
        severity: DriftSeverity,
        detected_at: Optional[datetime] = None,
    ) -> None:
        """Record a drift event for a node."""
        self._history.append(
            DriftHistoryEntry(
                node=node,
                severity=severity,
                detected_at=detected_at or datetime.now(UTC),
            )
        )

    def record_resolution(
        self, node: Node, resolution_time_seconds: float
    ) -> None:
        """Mark the most recent drift for a node as resolved."""
        for entry in reversed(self._history):
            if entry.node == node and not entry.resolved:
                entry.resolved = True
                entry.resolution_time_seconds = resolution_time_seconds
                break

    def assess_risk(self, node: Node) -> RiskScore:
        """Produce a risk score for a node based on drift history."""
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=self._window_hours)

        # Filter history for this node within window
        relevant = [
            e
            for e in self._history
            if e.node == node and e.detected_at >= window_start
        ]

        if not relevant:
            return RiskScore(
                node=node,
                score=0.0,
                level=RiskLevel.LOW,
                factors={"frequency": 0.0, "recency": 0.0, "severity": 0.0},
                predicted_drift_probability=0.05,
            )

        # Factor 1: Frequency (more drifts = higher risk)
        frequency_score = min(1.0, len(relevant) / 10.0)

        # Factor 2: Recency (recent drift = higher risk)
        most_recent = max(e.detected_at for e in relevant)
        hours_since = (now - most_recent).total_seconds() / 3600
        recency_score = max(0.0, 1.0 - hours_since / self._window_hours)

        # Factor 3: Severity (higher severity events = higher risk)
        severity_weights = {
            DriftSeverity.LOW: 0.1,
            DriftSeverity.MEDIUM: 0.3,
            DriftSeverity.HIGH: 0.7,
            DriftSeverity.CRITICAL: 1.0,
        }
        max_severity = max(severity_weights.get(e.severity, 0.0) for e in relevant)

        # Weighted composite score
        score = (
            frequency_score * 0.3
            + recency_score * 0.4
            + max_severity * 0.3
        )

        # Determine risk level
        if score >= 0.8:
            level = RiskLevel.CRITICAL
        elif score >= 0.5:
            level = RiskLevel.HIGH
        elif score >= 0.25:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return RiskScore(
            node=node,
            score=round(score, 3),
            level=level,
            factors={
                "frequency": round(frequency_score, 3),
                "recency": round(recency_score, 3),
                "severity": round(max_severity, 3),
            },
            predicted_drift_probability=round(min(1.0, score * 1.2), 3),
        )

    def assess_fleet(self, nodes: list[Node]) -> list[RiskScore]:
        """Assess risk for all nodes, sorted by risk (highest first)."""
        scores = [self.assess_risk(node) for node in nodes]
        return sorted(scores, key=lambda s: s.score, reverse=True)

    def detect_trend(self, node: Node, bucket_hours: int = 24) -> list[int]:
        """Return drift counts per time bucket (oldest first).

        Useful for detecting increasing/decreasing drift trends.
        """
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=self._window_hours)

        relevant = [
            e for e in self._history
            if e.node == node and e.detected_at >= window_start
        ]

        num_buckets = max(1, self._window_hours // bucket_hours)
        buckets = [0] * num_buckets

        for entry in relevant:
            hours_ago = (now - entry.detected_at).total_seconds() / 3600
            bucket_idx = min(num_buckets - 1, int(hours_ago / bucket_hours))
            # Reverse index so oldest is first
            buckets[num_buckets - 1 - bucket_idx] += 1

        return buckets

    def is_trending_up(self, node: Node, bucket_hours: int = 24) -> bool:
        """Check if drift frequency is increasing over time."""
        trend = self.detect_trend(node, bucket_hours)
        if len(trend) < 2:
            return False
        # Compare second half average to first half average
        mid = len(trend) // 2
        first_half = sum(trend[:mid]) / max(1, mid)
        second_half = sum(trend[mid:]) / max(1, len(trend) - mid)
        return second_half > first_half * 1.5

    def mean_time_to_resolution(self, node: Node) -> Optional[float]:
        """Calculate average resolution time in seconds for a node."""
        resolved = [
            e for e in self._history
            if e.node == node and e.resolved and e.resolution_time_seconds is not None
        ]
        if not resolved:
            return None
        return sum(e.resolution_time_seconds for e in resolved) / len(resolved)

    def fleet_risk_summary(self, nodes: list[Node]) -> dict[str, int]:
        """Return count of nodes at each risk level."""
        scores = self.assess_fleet(nodes)
        summary: dict[str, int] = {level.name: 0 for level in RiskLevel}
        for score in scores:
            summary[score.level.name] += 1
        return summary
