"""
Remote Executor Port

Architectural Intent:
- Port interface for executing commands on remote infrastructure
- Defines contract for remote execution capabilities
- Implemented by adapters (Fabric, MCP, SSH, etc.)
"""

from typing import Protocol, runtime_checkable, Optional
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash


@runtime_checkable
class RemoteExecutorPort(Protocol):
    """Port interface for executing commands on remote infrastructure."""

    async def sync_closure(self, nodes: list[Node], closure_path: str) -> bool: ...

    async def exec_command(self, nodes: list[Node], command: str) -> bool: ...

    async def get_current_hash(self, node: Node) -> Optional[NixHash]: ...

    async def rollback(
        self, nodes: list[Node], generation: Optional[str] = None
    ) -> bool: ...
