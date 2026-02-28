"""
SLO/SLA Engine

Architectural Intent:
- Service Level Objective entity for tracking availability targets
- Tracks violation windows and error budget consumption
- Immutable value objects for SLO reports

Design Decisions:
- SLO is an entity (has identity by name)
- SLOReport is a value object (snapshot in time)
- Error budget calculated as remaining percentage of allowed downtime
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum, auto
from typing import Optional


class SLOStatus(Enum):
    HEALTHY = auto()
    AT_RISK = auto()
    VIOLATED = auto()
    EXHAUSTED = auto()


@dataclass(frozen=True)
class SLOReport:
    """Point-in-time SLO status report."""

    slo_name: str
    target_availability: float
    actual_availability: float
    error_budget_remaining: float
    status: SLOStatus
    window_start: datetime
    window_end: datetime
    total_violations: int = 0
    longest_violation_minutes: float = 0.0

    @property
    def is_healthy(self) -> bool:
        return self.status == SLOStatus.HEALTHY

    @property
    def budget_consumed_percent(self) -> float:
        return max(0.0, 100.0 - self.error_budget_remaining)


@dataclass
class SLO:
    """Service Level Objective entity."""

    name: str
    target_availability: float  # e.g. 99.9
    window_hours: int = 720  # 30 days
    _violations: list[tuple[datetime, datetime]] = field(
        default_factory=list, repr=False
    )

    def __post_init__(self) -> None:
        if not (0 < self.target_availability <= 100):
            raise ValueError(
                f"target_availability must be 0-100, got {self.target_availability}"
            )

    def record_violation(
        self, start: datetime, end: Optional[datetime] = None
    ) -> None:
        """Record a violation window."""
        end = end or datetime.now(UTC)
        self._violations.append((start, end))

    def report(self, now: Optional[datetime] = None) -> SLOReport:
        """Generate current SLO report."""
        now = now or datetime.now(UTC)
        window_start = now - timedelta(hours=self.window_hours)
        window_minutes = self.window_hours * 60

        # Calculate total violation minutes in window
        total_violation_minutes = 0.0
        longest = 0.0
        violations_in_window = 0

        for start, end in self._violations:
            # Clip to window
            v_start = max(start, window_start)
            v_end = min(end, now)
            if v_start < v_end:
                duration = (v_end - v_start).total_seconds() / 60
                total_violation_minutes += duration
                longest = max(longest, duration)
                violations_in_window += 1

        actual_availability = (
            (window_minutes - total_violation_minutes) / window_minutes * 100
        )

        # Error budget: allowed downtime minus actual downtime
        allowed_downtime = window_minutes * (1 - self.target_availability / 100)
        remaining = max(0.0, allowed_downtime - total_violation_minutes)
        error_budget_remaining = (
            (remaining / allowed_downtime * 100) if allowed_downtime > 0 else 100.0
        )

        if error_budget_remaining <= 0:
            status = SLOStatus.EXHAUSTED
        elif actual_availability < self.target_availability:
            status = SLOStatus.VIOLATED
        elif error_budget_remaining < 20:
            status = SLOStatus.AT_RISK
        else:
            status = SLOStatus.HEALTHY

        return SLOReport(
            slo_name=self.name,
            target_availability=self.target_availability,
            actual_availability=round(actual_availability, 4),
            error_budget_remaining=round(error_budget_remaining, 2),
            status=status,
            window_start=window_start,
            window_end=now,
            total_violations=violations_in_window,
            longest_violation_minutes=round(longest, 2),
        )
