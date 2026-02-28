"""Tests for PredictiveAnalyticsService."""

import pytest
from datetime import datetime, timedelta, UTC
from chimera.domain.services.predictive_analytics import (
    PredictiveAnalyticsService,
    RiskLevel,
)
from chimera.domain.services.drift_detection import DriftSeverity
from chimera.domain.value_objects.node import Node


class TestPredictiveAnalytics:
    def test_no_history_low_risk(self):
        service = PredictiveAnalyticsService()
        node = Node(host="10.0.0.1")
        score = service.assess_risk(node)
        assert score.level == RiskLevel.LOW
        assert score.score == 0.0

    def test_single_drift_event(self):
        service = PredictiveAnalyticsService()
        node = Node(host="10.0.0.1")
        service.record_drift(node, DriftSeverity.MEDIUM)
        score = service.assess_risk(node)
        assert score.score > 0

    def test_frequent_drifts_higher_risk(self):
        service = PredictiveAnalyticsService()
        node = Node(host="10.0.0.1")
        now = datetime.now(UTC)
        for i in range(5):
            service.record_drift(
                node,
                DriftSeverity.HIGH,
                detected_at=now - timedelta(hours=i),
            )
        score = service.assess_risk(node)
        assert score.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_old_drifts_lower_risk(self):
        service = PredictiveAnalyticsService(history_window_hours=24)
        node = Node(host="10.0.0.1")
        # Drift 20 hours ago
        service.record_drift(
            node,
            DriftSeverity.MEDIUM,
            detected_at=datetime.now(UTC) - timedelta(hours=20),
        )
        score = service.assess_risk(node)
        # Recency score should be low
        assert score.factors["recency"] < 0.5

    def test_fleet_assessment(self):
        service = PredictiveAnalyticsService()
        nodes = [Node(host="10.0.0.1"), Node(host="10.0.0.2")]
        service.record_drift(nodes[0], DriftSeverity.CRITICAL)
        scores = service.assess_fleet(nodes)
        assert len(scores) == 2
        assert scores[0].node == nodes[0]  # higher risk first

    def test_record_resolution(self):
        service = PredictiveAnalyticsService()
        node = Node(host="10.0.0.1")
        service.record_drift(node, DriftSeverity.HIGH)
        service.record_resolution(node, 120.0)
        assert service._history[0].resolved
        assert service._history[0].resolution_time_seconds == 120.0

    def test_different_nodes_independent(self):
        service = PredictiveAnalyticsService()
        node_a = Node(host="10.0.0.1")
        node_b = Node(host="10.0.0.2")
        service.record_drift(node_a, DriftSeverity.CRITICAL)
        score_b = service.assess_risk(node_b)
        assert score_b.score == 0.0
