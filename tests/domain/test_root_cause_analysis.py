"""Tests for RootCauseAnalyzer."""

import pytest
from datetime import datetime, timedelta, UTC

from chimera.domain.services.root_cause_analysis import (
    CausalFactor,
    CausalChain,
    CauseCategory,
    RootCauseAnalyzer,
    RootCauseReport,
)
from chimera.infrastructure.agent.chimera_agent import (
    DriftReport,
    DriftSeverity,
    NodeHealth,
    AgentStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drift(
    node_id: str,
    detected_at: datetime | None = None,
    severity: DriftSeverity = DriftSeverity.HIGH,
) -> DriftReport:
    return DriftReport(
        node_id=node_id,
        expected_hash="aaa",
        actual_hash="bbb",
        severity=severity,
        detected_at=detected_at or datetime.now(UTC),
        details="test drift",
    )


def _make_health(
    node_id: str,
    status: AgentStatus = AgentStatus.HEALTHY,
) -> NodeHealth:
    return NodeHealth(node_id=node_id, status=status)


# ---------------------------------------------------------------------------
# Value object tests
# ---------------------------------------------------------------------------

class TestCausalFactor:
    def test_valid_weight(self):
        f = CausalFactor(description="test", weight=0.5, evidence="ev")
        assert f.weight == 0.5

    def test_invalid_weight_raises(self):
        with pytest.raises(ValueError, match="Weight must be"):
            CausalFactor(description="test", weight=1.5)

    def test_frozen(self):
        f = CausalFactor(description="test", weight=0.5)
        with pytest.raises(AttributeError):
            f.weight = 0.9  # type: ignore[misc]


class TestCausalChain:
    def test_root_and_symptom(self):
        chain = CausalChain(
            steps=("cause", "intermediate", "symptom"),
            affected_node_ids=frozenset({"n1"}),
        )
        assert chain.root == "cause"
        assert chain.symptom == "symptom"
        assert chain.depth == 3

    def test_empty_chain(self):
        chain = CausalChain(steps=())
        assert chain.root == ""
        assert chain.symptom == ""
        assert chain.depth == 0


class TestRootCauseReport:
    def test_confidence_validation(self):
        with pytest.raises(ValueError, match="Confidence must be"):
            RootCauseReport(
                probable_cause=CauseCategory.UNKNOWN,
                confidence=1.5,
                summary="bad",
                causal_chain=CausalChain(steps=()),
                contributing_factors=(),
                affected_node_ids=frozenset(),
            )

    def test_high_confidence_property(self):
        report = RootCauseReport(
            probable_cause=CauseCategory.LOCAL_ISSUE,
            confidence=0.8,
            summary="ok",
            causal_chain=CausalChain(steps=("a",)),
            contributing_factors=(),
            affected_node_ids=frozenset({"n1"}),
        )
        assert report.is_high_confidence is True

    def test_low_confidence_property(self):
        report = RootCauseReport(
            probable_cause=CauseCategory.UNKNOWN,
            confidence=0.3,
            summary="low",
            causal_chain=CausalChain(steps=("a",)),
            contributing_factors=(),
            affected_node_ids=frozenset(),
        )
        assert report.is_high_confidence is False


# ---------------------------------------------------------------------------
# Analyzer: single node drift -> local cause
# ---------------------------------------------------------------------------

class TestSingleNodeDrift:
    def test_single_node_classified_as_local(self):
        analyzer = RootCauseAnalyzer()
        reports = [_make_drift("node-1")]
        health = [_make_health("node-1", AgentStatus.DRIFT_DETECTED)]

        result = analyzer.analyze(reports, health)

        assert result.probable_cause == CauseCategory.LOCAL_ISSUE
        assert "node-1" in result.affected_node_ids
        assert len(result.affected_node_ids) == 1

    def test_single_node_causal_chain_references_node(self):
        analyzer = RootCauseAnalyzer()
        reports = [_make_drift("web-01")]
        health = [_make_health("web-01")]

        result = analyzer.analyze(reports, health)

        assert "web-01" in result.causal_chain.symptom
        assert result.causal_chain.depth >= 2


# ---------------------------------------------------------------------------
# Analyzer: multi-node simultaneous drift -> upstream cause
# ---------------------------------------------------------------------------

class TestMultiNodeDrift:
    def test_simultaneous_drift_classified_as_upstream(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift("node-1", detected_at=now),
            _make_drift("node-2", detected_at=now + timedelta(seconds=5)),
            _make_drift("node-3", detected_at=now + timedelta(seconds=10)),
        ]
        health = [
            _make_health("node-1", AgentStatus.DRIFT_DETECTED),
            _make_health("node-2", AgentStatus.DRIFT_DETECTED),
            _make_health("node-3", AgentStatus.DRIFT_DETECTED),
        ]

        result = analyzer.analyze(reports, health)

        assert result.probable_cause == CauseCategory.UPSTREAM_CONFIG_CHANGE
        assert len(result.affected_node_ids) == 3

    def test_upstream_causal_chain_mentions_propagation(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift("n1", detected_at=now),
            _make_drift("n2", detected_at=now + timedelta(seconds=2)),
        ]
        health = [_make_health("n1"), _make_health("n2")]

        result = analyzer.analyze(reports, health)

        assert result.probable_cause == CauseCategory.UPSTREAM_CONFIG_CHANGE
        chain_text = " ".join(result.causal_chain.steps).lower()
        assert "propagat" in chain_text or "upstream" in chain_text

    def test_widely_separated_drifts_still_upstream_if_multi_node(self):
        """Multiple nodes drifting, even across time windows, are classified
        as upstream because multi-node drift is inherently suspicious."""
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift("n1", detected_at=now),
            _make_drift("n2", detected_at=now + timedelta(minutes=5)),
        ]
        health = [_make_health("n1"), _make_health("n2")]

        result = analyzer.analyze(reports, health)

        # Multi-node -> upstream (fallback classification)
        assert result.probable_cause == CauseCategory.UPSTREAM_CONFIG_CHANGE


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    def test_more_signals_increase_confidence(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()

        # Few signals: single node, no deploy, no groups
        single = analyzer.analyze(
            [_make_drift("n1", detected_at=now)],
            [_make_health("n1")],
        )

        # Many signals: multi-node + deploy + spatial
        multi = analyzer.analyze(
            [
                _make_drift("n1", detected_at=now),
                _make_drift("n2", detected_at=now + timedelta(seconds=3)),
                _make_drift("n3", detected_at=now + timedelta(seconds=5)),
            ],
            [
                _make_health("n1", AgentStatus.DRIFT_DETECTED),
                _make_health("n2", AgentStatus.DRIFT_DETECTED),
                _make_health("n3", AgentStatus.DEGRADED),
            ],
            deploy_timestamps=[now - timedelta(seconds=10)],
            node_groups={"n1": "subnet-a", "n2": "subnet-a", "n3": "subnet-a"},
        )

        assert multi.confidence > single.confidence

    def test_empty_reports_zero_confidence(self):
        analyzer = RootCauseAnalyzer()
        result = analyzer.analyze([], [])
        assert result.confidence == 0.0
        assert result.probable_cause == CauseCategory.UNKNOWN

    def test_confidence_bounded_to_one(self):
        """Even with many signals, confidence must not exceed 1.0."""
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift(f"n{i}", detected_at=now + timedelta(seconds=i))
            for i in range(20)
        ]
        health = [
            _make_health(f"n{i}", AgentStatus.DRIFT_DETECTED)
            for i in range(20)
        ]
        result = analyzer.analyze(
            reports,
            health,
            deploy_timestamps=[now],
            node_groups={f"n{i}": "same-group" for i in range(20)},
        )
        assert result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Causal chain construction
# ---------------------------------------------------------------------------

class TestCausalChainConstruction:
    def test_local_chain_has_minimum_depth(self):
        analyzer = RootCauseAnalyzer()
        result = analyzer.analyze(
            [_make_drift("solo")],
            [_make_health("solo")],
        )
        assert result.causal_chain.depth >= 2

    def test_upstream_chain_includes_all_affected(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift("a", detected_at=now),
            _make_drift("b", detected_at=now),
        ]
        result = analyzer.analyze(reports, [])

        assert result.causal_chain.affected_node_ids == frozenset({"a", "b"})

    def test_deploy_related_chain(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift("d1", detected_at=now + timedelta(seconds=5)),
        ]
        result = analyzer.analyze(
            reports,
            [_make_health("d1")],
            deploy_timestamps=[now],
        )

        assert result.probable_cause == CauseCategory.DEPLOY_RELATED
        chain_text = " ".join(result.causal_chain.steps).lower()
        assert "deploy" in chain_text


# ---------------------------------------------------------------------------
# Deploy-related detection
# ---------------------------------------------------------------------------

class TestDeployRelated:
    def test_drift_shortly_after_deploy(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [_make_drift("n1", detected_at=now + timedelta(seconds=10))]
        health = [_make_health("n1")]

        result = analyzer.analyze(
            reports, health, deploy_timestamps=[now]
        )

        assert result.probable_cause == CauseCategory.DEPLOY_RELATED

    def test_drift_long_after_deploy_not_deploy_related(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [_make_drift("n1", detected_at=now + timedelta(hours=1))]
        health = [_make_health("n1")]

        result = analyzer.analyze(
            reports, health, deploy_timestamps=[now]
        )

        # Should be local, not deploy-related (too far away)
        assert result.probable_cause != CauseCategory.DEPLOY_RELATED


# ---------------------------------------------------------------------------
# Network partition detection
# ---------------------------------------------------------------------------

class TestNetworkPartition:
    def test_unreachable_nodes_signal_partition(self):
        analyzer = RootCauseAnalyzer()
        reports = [_make_drift("n1"), _make_drift("n2")]
        health = [
            _make_health("n1", AgentStatus.UNREACHABLE),
            _make_health("n2", AgentStatus.UNREACHABLE),
            _make_health("n3", AgentStatus.UNREACHABLE),
        ]

        result = analyzer.analyze(reports, health)

        assert result.probable_cause == CauseCategory.NETWORK_PARTITION


# ---------------------------------------------------------------------------
# Spatial correlation
# ---------------------------------------------------------------------------

class TestSpatialCorrelation:
    def test_same_group_adds_factor(self):
        now = datetime.now(UTC)
        analyzer = RootCauseAnalyzer()
        reports = [
            _make_drift("n1", detected_at=now),
            _make_drift("n2", detected_at=now),
        ]
        node_groups = {"n1": "rack-a", "n2": "rack-a"}

        result = analyzer.analyze(
            reports, [], node_groups=node_groups
        )

        spatial_factors = [
            f for f in result.contributing_factors
            if "group" in f.description.lower()
        ]
        assert len(spatial_factors) >= 1
