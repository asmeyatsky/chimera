"""
Composition Root

Architectural Intent:
- Dependency injection composition root for the Chimera application
- Single place where all adapters and use cases are wired together
- No adapter instantiation should occur outside this module (except CLI)

Design Decisions:
- Uses a simple dataclass container instead of a DI framework
- Factory function creates and wires all dependencies
- Lazy initialization for optional components (MCP, OTEL)
"""

from dataclasses import dataclass
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.infrastructure.event_bus import EventBus
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.application.use_cases.execute_local_deployment import ExecuteLocalDeployment
from chimera.application.use_cases.rollback_deployment import RollbackDeployment
from chimera.application.use_cases.autonomous_loop import AutonomousLoop


@dataclass
class ChimeraContainer:
    """DI container holding all wired dependencies."""

    nix_adapter: NixAdapter
    tmux_adapter: TmuxAdapter
    fabric_adapter: FabricAdapter
    event_bus: EventBus
    deploy_fleet: DeployFleet
    execute_local: ExecuteLocalDeployment
    rollback: RollbackDeployment
    autonomous_loop: AutonomousLoop


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

    return ChimeraContainer(
        nix_adapter=nix_adapter,
        tmux_adapter=tmux_adapter,
        fabric_adapter=fabric_adapter,
        event_bus=event_bus,
        deploy_fleet=deploy_fleet,
        execute_local=execute_local,
        rollback=rollback,
        autonomous_loop=autonomous_loop,
    )
