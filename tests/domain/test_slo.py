"""Tests for SLO entity."""

import pytest
from datetime import datetime, timedelta, UTC
from chimera.domain.entities.slo import SLO, SLOStatus


class TestSLO:
    def test_healthy_slo(self):
        slo = SLO(name="api-availability", target_availability=99.9)
        report = slo.report()
        assert report.status == SLOStatus.HEALTHY
        assert report.actual_availability == 100.0
        assert report.error_budget_remaining == 100.0

    def test_violated_slo(self):
        slo = SLO(name="api-availability", target_availability=99.9, window_hours=24)
        now = datetime.now(UTC)
        # 30 minutes of downtime in a 24h window
        slo.record_violation(now - timedelta(hours=1), now - timedelta(minutes=30))
        report = slo.report(now)
        assert report.total_violations == 1
        assert report.actual_availability < 100.0

    def test_exhausted_budget(self):
        slo = SLO(name="api-availability", target_availability=99.9, window_hours=24)
        now = datetime.now(UTC)
        # More downtime than allowed (~1.44 min allowed for 99.9% in 24h)
        slo.record_violation(now - timedelta(hours=2), now - timedelta(hours=1))
        report = slo.report(now)
        assert report.status in (SLOStatus.VIOLATED, SLOStatus.EXHAUSTED)

    def test_invalid_target(self):
        with pytest.raises(ValueError, match="target_availability"):
            SLO(name="bad", target_availability=0)

    def test_invalid_target_over_100(self):
        with pytest.raises(ValueError, match="target_availability"):
            SLO(name="bad", target_availability=101)

    def test_report_budget_consumed(self):
        slo = SLO(name="test", target_availability=99.0, window_hours=24)
        report = slo.report()
        assert report.budget_consumed_percent == 0.0

    def test_multiple_violations(self):
        slo = SLO(name="test", target_availability=99.0, window_hours=24)
        now = datetime.now(UTC)
        slo.record_violation(now - timedelta(hours=3), now - timedelta(hours=2, minutes=50))
        slo.record_violation(now - timedelta(hours=1), now - timedelta(minutes=55))
        report = slo.report(now)
        assert report.total_violations == 2
