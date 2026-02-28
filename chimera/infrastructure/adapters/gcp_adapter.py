"""
GCP Cloud Provider Adapter

Architectural Intent:
- Implements CloudProviderPort for Google Cloud Platform
- Stub implementation for future GCP SDK integration
"""

import logging
from typing import Optional, Any
from chimera.domain.value_objects.node import Node

logger = logging.getLogger(__name__)


class GCPAdapter:
    """GCP cloud provider adapter (stub)."""

    async def discover_nodes(
        self, filters: Optional[dict[str, str]] = None
    ) -> list[Node]:
        logger.info("GCP discover_nodes called (stub)")
        return []

    async def provision_node(
        self,
        name: str,
        instance_type: str = "e2-micro",
        region: str = "us-central1",
        **kwargs: Any,
    ) -> Node:
        raise NotImplementedError("GCP provisioning not yet implemented")

    async def decommission_node(self, node: Node) -> bool:
        raise NotImplementedError("GCP decommissioning not yet implemented")

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        return {"provider": "gcp", "host": node.host}
