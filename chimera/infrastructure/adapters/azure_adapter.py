"""
Azure Cloud Provider Adapter

Architectural Intent:
- Implements CloudProviderPort for Microsoft Azure
- Stub implementation for future Azure SDK integration
"""

import logging
from typing import Optional, Any
from chimera.domain.value_objects.node import Node

logger = logging.getLogger(__name__)


class AzureAdapter:
    """Azure cloud provider adapter (stub)."""

    async def discover_nodes(
        self, filters: Optional[dict[str, str]] = None
    ) -> list[Node]:
        logger.info("Azure discover_nodes called (stub)")
        return []

    async def provision_node(
        self,
        name: str,
        instance_type: str = "Standard_B1s",
        region: str = "eastus",
        **kwargs: Any,
    ) -> Node:
        raise NotImplementedError("Azure provisioning not yet implemented")

    async def decommission_node(self, node: Node) -> bool:
        raise NotImplementedError("Azure decommissioning not yet implemented")

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        return {"provider": "azure", "host": node.host}
