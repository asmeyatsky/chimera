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

    def test_detect_trend(self):
        service = PredictiveAnalyticsService(history_window_hours=72)
        node = Node(host="10.0.0.1")
        now = datetime.now(UTC)
        # 1 drift 60 hours ago, 3 drifts in last 12 hours
        service.record_drift(node, DriftSeverity.LOW, detected_at=now - timedelta(hours=60))
        for i in range(3):
            service.record_drift(node, DriftSeverity.HIGH, detected_at=now - timedelta(hours=i))
        trend = service.detect_trend(node, bucket_hours=24)
        assert len(trend) == 3
        # Last bucket should have more drifts than first
        assert trend[-1] > trend[0]

    def test_is_trending_up(self):
        service = PredictiveAnalyticsService(history_window_hours=48)
        node = Node(host="10.0.0.1")
        now = datetime.now(UTC)
        # No drifts in first half, many in second half
        for i in range(5):
            service.record_drift(node, DriftSeverity.HIGH, detected_at=now - timedelta(hours=i))
        assert service.is_trending_up(node, bucket_hours=24) is True

    def test_not_trending_up_stable(self):
        service = PredictiveAnalyticsService(history_window_hours=48)
        node = Node(host="10.0.0.1")
        assert service.is_trending_up(node) is False

    def test_mean_time_to_resolution(self):
        service = PredictiveAnalyticsService()
        node = Node(host="10.0.0.1")
        service.record_drift(node, DriftSeverity.HIGH)
        service.record_resolution(node, 60.0)
        service.record_drift(node, DriftSeverity.HIGH)
        service.record_resolution(node, 120.0)
        mttr = service.mean_time_to_resolution(node)
        assert mttr == 90.0

    def test_mean_time_to_resolution_no_data(self):
        service = PredictiveAnalyticsService()
        node = Node(host="10.0.0.1")
        assert service.mean_time_to_resolution(node) is None

    def test_fleet_risk_summary(self):
        service = PredictiveAnalyticsService()
        nodes = [Node(host="10.0.0.1"), Node(host="10.0.0.2"), Node(host="10.0.0.3")]
        service.record_drift(nodes[0], DriftSeverity.CRITICAL)
        summary = service.fleet_risk_summary(nodes)
        assert sum(summary.values()) == 3
        assert "LOW" in summary
