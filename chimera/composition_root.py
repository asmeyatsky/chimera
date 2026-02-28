"""
Composition Root

Architectural Intent:
- Dependency injection composition root for the Chimera application
- Single place where all adapters and use cases are wired together
- No adapter instantiation should occur outside this module

Design Decisions:
- Uses a simple dataclass container instead of a DI framework
- Factory function creates and wires all dependencies
- Lazy initialization for optional components (MCP, OTEL)
"""

from dataclasses import dataclass, field
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.infrastructure.event_bus import EventBus
from chimera.infrastructure.agent.agent_registry import AgentRegistry
from chimera.infrastructure.repositories.playbook_repository import PlaybookRepository
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.application.use_cases.execute_local_deployment import ExecuteLocalDeployment
from chimera.application.use_cases.rollback_deployment import RollbackDeployment
from chimera.application.use_cases.autonomous_loop import AutonomousLoop
from chimera.domain.services.predictive_analytics import PredictiveAnalyticsService


@dataclass
class ChimeraContainer:
    """DI container holding all wired dependencies."""

    # Adapters
    nix_adapter: NixAdapter
    tmux_adapter: TmuxAdapter
    fabric_adapter: FabricAdapter
    event_bus: EventBus

    # Use cases
    deploy_fleet: DeployFleet
    execute_local: ExecuteLocalDeployment
    rollback: RollbackDeployment
    autonomous_loop: AutonomousLoop

    # Subsystems
    agent_registry: AgentRegistry
    playbook_repository: PlaybookRepository
    predictive_analytics: PredictiveAnalyticsService


def create_container() -> ChimeraContainer:
    """Create and wire all dependencies."""
    nix_adapter = NixAdapter()
    tmux_adapter = TmuxAdapter()
    fabric_adapter = FabricAdapter()
    event_bus = EventBus()

    deploy_fleet = DeployFleet(nix_adapter, fabric_adapter)
    execute_local = ExecuteLocalDeployment(nix_adapter, tmux_adapter)
    rollback = RollbackDeployment(fabric_adapter)
    autonomous_loop = AutonomousLoop(nix_adapter, fabric_adapter, deploy_fleet)

    agent_registry = AgentRegistry()
    playbook_repository = PlaybookRepository()
    predictive_analytics = PredictiveAnalyticsService()

    return ChimeraContainer(
        nix_adapter=nix_adapter,
        tmux_adapter=tmux_adapter,
        fabric_adapter=fabric_adapter,
        event_bus=event_bus,
        deploy_fleet=deploy_fleet,
        execute_local=execute_local,
        rollback=rollback,
        autonomous_loop=autonomous_loop,
        agent_registry=agent_registry,
        playbook_repository=playbook_repository,
        predictive_analytics=predictive_analytics,
    )
