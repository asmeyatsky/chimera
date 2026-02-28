"""
Cloud Provider Port

Architectural Intent:
- Port interface for multi-cloud infrastructure management
- Abstracts cloud-specific node discovery, provisioning, and decommissioning
- Implemented by AWS, GCP, Azure adapters

Design Decisions:
- Uses Protocol for structural typing (no inheritance needed)
- Methods cover the core lifecycle: discover, provision, decommission, metadata
"""

from typing import Protocol, runtime_checkable, Optional, Any
from chimera.domain.value_objects.node import Node


@runtime_checkable
class CloudProviderPort(Protocol):
    """Port for cloud provider infrastructure operations."""

    async def discover_nodes(self, filters: Optional[dict[str, str]] = None) -> list[Node]:
        """Discover existing nodes matching the given filters."""
        ...

    async def provision_node(
        self,
        name: str,
        instance_type: str = "t3.micro",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> Node:
        """Provision a new node and return its connection details."""
        ...

    async def decommission_node(self, node: Node) -> bool:
        """Decommission (terminate) a node. Returns True on success."""
        ...

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        """Get cloud-specific metadata for a node."""
        ...
