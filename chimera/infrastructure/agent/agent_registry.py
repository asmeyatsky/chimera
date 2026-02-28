"""
Agent Registry

Architectural Intent:
- Central registry tracking all connected agents and their state
- Used by the orchestrator to monitor fleet health
- Provides fleet-wide queries (all drifted, all healthy, etc.)
- Stores healing commands for agents to pick up
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Optional
import logging

from chimera.infrastructure.agent.chimera_agent import (
    NodeHealth,
    DriftReport,
    AgentStatus,
)

logger = logging.getLogger(__name__)

# Agents not reporting within this window are considered stale
STALE_THRESHOLD = timedelta(seconds=60)


@dataclass
class AgentRecord:
    """Tracked state for a single agent."""
    node_id: str
    health: Optional[NodeHealth] = None
    drift_report: Optional[DriftReport] = None
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    pending_healing_command: Optional[str] = None

    @property
    def is_stale(self) -> bool:
        return (datetime.now(UTC) - self.last_seen) > STALE_THRESHOLD


class AgentRegistry:
    """Registry of all agents in the fleet."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}

    def register(self, node_id: str) -> AgentRecord:
        """Register a new agent or return existing record."""
        if node_id not in self._agents:
            self._agents[node_id] = AgentRecord(node_id=node_id)
            logger.info("Agent registered: %s", node_id)
        return self._agents[node_id]

    def update_health(self, health: NodeHealth) -> None:
        """Update health report from an agent."""
        record = self.register(health.node_id)
        record.health = health
        record.last_seen = datetime.now(UTC)

    def update_drift(self, report: DriftReport) -> None:
        """Record drift report from an agent."""
        record = self.register(report.node_id)
        record.drift_report = report
        record.last_seen = datetime.now(UTC)

    def set_healing_command(self, node_id: str, command: str) -> None:
        """Queue a healing command for an agent to pick up."""
        record = self.register(node_id)
        record.pending_healing_command = command

    def pop_healing_command(self, node_id: str) -> Optional[str]:
        """Retrieve and clear pending healing command for an agent."""
        record = self._agents.get(node_id)
        if record and record.pending_healing_command:
            cmd = record.pending_healing_command
            record.pending_healing_command = None
            return cmd
        return None

    def acknowledge_healing(self, node_id: str, success: bool) -> None:
        """Record healing result."""
        record = self._agents.get(node_id)
        if record:
            record.last_seen = datetime.now(UTC)
            if success:
                record.drift_report = None
                logger.info("Agent %s healed successfully", node_id)
            else:
                logger.warning("Agent %s healing failed", node_id)

    def get_all(self) -> list[AgentRecord]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_healthy(self) -> list[AgentRecord]:
        """Get agents reporting healthy status."""
        return [
            r for r in self._agents.values()
            if r.health and r.health.status == AgentStatus.HEALTHY
            and not r.is_stale
        ]

    def get_drifted(self) -> list[AgentRecord]:
        """Get agents with active drift."""
        return [
            r for r in self._agents.values()
            if r.health and r.health.status == AgentStatus.DRIFT_DETECTED
            and not r.is_stale
        ]

    def get_stale(self) -> list[AgentRecord]:
        """Get agents that haven't reported recently."""
        return [r for r in self._agents.values() if r.is_stale]

    def get(self, node_id: str) -> Optional[AgentRecord]:
        """Get a specific agent record."""
        return self._agents.get(node_id)

    def remove(self, node_id: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(node_id, None)

    @property
    def total_count(self) -> int:
        return len(self._agents)

    @property
    def healthy_count(self) -> int:
        return len(self.get_healthy())

    @property
    def drifted_count(self) -> int:
        return len(self.get_drifted())
