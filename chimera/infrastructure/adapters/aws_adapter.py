"""
AWS Cloud Provider Adapter

Architectural Intent:
- Implements CloudProviderPort for AWS EC2
- Stub implementation for future AWS SDK integration
"""

import logging
from typing import Optional, Any
from chimera.domain.value_objects.node import Node

logger = logging.getLogger(__name__)


class AWSAdapter:
    """AWS cloud provider adapter (stub)."""

    async def discover_nodes(
        self, filters: Optional[dict[str, str]] = None
    ) -> list[Node]:
        logger.info("AWS discover_nodes called (stub)")
        return []

    async def provision_node(
        self,
        name: str,
        instance_type: str = "t3.micro",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> Node:
        raise NotImplementedError("AWS provisioning not yet implemented")

    async def decommission_node(self, node: Node) -> bool:
        raise NotImplementedError("AWS decommissioning not yet implemented")

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        return {"provider": "aws", "host": node.host}
