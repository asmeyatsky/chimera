"""Tests for cloud provider adapters."""

import pytest
from chimera.infrastructure.adapters.aws_adapter import AWSAdapter
from chimera.infrastructure.adapters.gcp_adapter import GCPAdapter
from chimera.infrastructure.adapters.azure_adapter import AzureAdapter
from chimera.domain.value_objects.node import Node


class TestAWSAdapter:
    @pytest.mark.asyncio
    async def test_discover_nodes_returns_empty(self):
        adapter = AWSAdapter()
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_provision_not_implemented(self):
        adapter = AWSAdapter()
        with pytest.raises(NotImplementedError):
            await adapter.provision_node("test-node")

    @pytest.mark.asyncio
    async def test_get_metadata(self):
        adapter = AWSAdapter()
        node = Node(host="10.0.0.1")
        meta = await adapter.get_node_metadata(node)
        assert meta["provider"] == "aws"


class TestGCPAdapter:
    @pytest.mark.asyncio
    async def test_discover_nodes_returns_empty(self):
        adapter = GCPAdapter()
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_provision_not_implemented(self):
        adapter = GCPAdapter()
        with pytest.raises(NotImplementedError):
            await adapter.provision_node("test-node")

    @pytest.mark.asyncio
    async def test_get_metadata(self):
        adapter = GCPAdapter()
        node = Node(host="10.0.0.1")
        meta = await adapter.get_node_metadata(node)
        assert meta["provider"] == "gcp"


class TestAzureAdapter:
    @pytest.mark.asyncio
    async def test_discover_nodes_returns_empty(self):
        adapter = AzureAdapter()
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_provision_not_implemented(self):
        adapter = AzureAdapter()
        with pytest.raises(NotImplementedError):
            await adapter.provision_node("test-node")

    @pytest.mark.asyncio
    async def test_get_metadata(self):
        adapter = AzureAdapter()
        node = Node(host="10.0.0.1")
        meta = await adapter.get_node_metadata(node)
        assert meta["provider"] == "azure"
