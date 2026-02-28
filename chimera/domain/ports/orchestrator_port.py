"""
Orchestrator Port

Architectural Intent:
- Protocol for agent-to-orchestrator communication
- Agents use this port to report health, drift, and receive commands
- Implementations can use MCP, gRPC, HTTP, or in-process calls
"""

from __future__ import annotations
from typing import Protocol, Optional, runtime_checkable

from chimera.infrastructure.agent.chimera_agent import NodeHealth, DriftReport


@runtime_checkable
class OrchestratorPort(Protocol):
    """Port for agent -> orchestrator communication."""

    async def report_health(self, health: NodeHealth) -> None:
        """Send heartbeat with health status to orchestrator."""
        ...

    async def report_drift(self, report: DriftReport) -> None:
        """Report configuration drift to orchestrator."""
        ...

    async def fetch_healing_command(self, node_id: str) -> Optional[str]:
        """Check if orchestrator has a healing command for this node."""
        ...

    async def acknowledge_healing(self, node_id: str, success: bool) -> None:
        """Report healing result back to orchestrator."""
        ...
