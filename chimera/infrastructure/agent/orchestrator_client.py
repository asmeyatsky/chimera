"""
Orchestrator Client

Architectural Intent:
- Implementation of OrchestratorPort for agent-side communication
- InProcessOrchestratorClient: direct calls to AgentRegistry (same process)
- MCPOrchestratorClient: calls via MCP to remote orchestrator
"""

from __future__ import annotations
from typing import Optional
import logging

from chimera.domain.ports.orchestrator_port import OrchestratorPort
from chimera.infrastructure.agent.chimera_agent import NodeHealth, DriftReport

logger = logging.getLogger(__name__)


class InProcessOrchestratorClient:
    """Orchestrator client for same-process communication.

    Used when agent and orchestrator run in the same process (e.g., testing,
    single-node deployments).
    """

    def __init__(self, registry: "AgentRegistry") -> None:
        from chimera.infrastructure.agent.agent_registry import AgentRegistry
        self._registry: AgentRegistry = registry

    async def report_health(self, health: NodeHealth) -> None:
        self._registry.update_health(health)

    async def report_drift(self, report: DriftReport) -> None:
        self._registry.update_drift(report)

    async def fetch_healing_command(self, node_id: str) -> Optional[str]:
        return self._registry.pop_healing_command(node_id)

    async def acknowledge_healing(self, node_id: str, success: bool) -> None:
        self._registry.acknowledge_healing(node_id, success)


class MCPOrchestratorClient:
    """Orchestrator client communicating via MCP.

    Used when agent runs on a remote node and communicates
    with the central orchestrator via MCP protocol.
    """

    def __init__(self, mcp_client: "MCPClient") -> None:
        from chimera.infrastructure.mcp_clients.remote_executor_client import MCPClient
        self._client: MCPClient = mcp_client

    async def report_health(self, health: NodeHealth) -> None:
        await self._client.call_tool(
            "report_health",
            arguments={
                "node_id": health.node_id,
                "status": health.status.name,
                "current_hash": health.current_hash,
                "expected_hash": health.expected_hash,
            },
        )

    async def report_drift(self, report: DriftReport) -> None:
        await self._client.call_tool(
            "report_drift",
            arguments={
                "node_id": report.node_id,
                "expected_hash": report.expected_hash,
                "actual_hash": report.actual_hash,
                "severity": report.severity.name,
                "details": report.details,
            },
        )

    async def fetch_healing_command(self, node_id: str) -> Optional[str]:
        result = await self._client.call_tool(
            "fetch_healing_command",
            arguments={"node_id": node_id},
        )
        return result.get("command")

    async def acknowledge_healing(self, node_id: str, success: bool) -> None:
        await self._client.call_tool(
            "acknowledge_healing",
            arguments={"node_id": node_id, "success": success},
        )
