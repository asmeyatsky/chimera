"""
Chimera Agent Infrastructure

Architectural Intent:
- Node-level agent for health monitoring and drift detection
- Exports telemetry via OpenTelemetry
- Communicates with central orchestrator
"""

from chimera.infrastructure.agent.chimera_agent import (
    ChimeraAgent,
    AgentConfig,
    AgentStatus,
    DriftSeverity,
    NodeHealth,
    DriftReport,
)
from chimera.infrastructure.agent.agent_registry import AgentRegistry, AgentRecord
from chimera.infrastructure.agent.orchestrator_client import (
    InProcessOrchestratorClient,
    MCPOrchestratorClient,
)

__all__ = [
    "ChimeraAgent",
    "AgentConfig",
    "AgentStatus",
    "DriftSeverity",
    "NodeHealth",
    "DriftReport",
    "AgentRegistry",
    "AgentRecord",
    "InProcessOrchestratorClient",
    "MCPOrchestratorClient",
]
