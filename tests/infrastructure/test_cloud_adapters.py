"""
Tests for cloud provider adapters.

Coverage strategy
-----------------
Each adapter is exercised through its full lifecycle:
  1. discover_nodes on an empty registry returns an empty list.
  2. provision_node returns a valid Node and populates the registry.
  3. discover_nodes after provisioning returns the new node.
  4. discover_nodes with matching tag/label filters includes the node.
  5. discover_nodes with non-matching filters excludes the node.
  6. get_node_metadata for a provisioned node returns enriched fields.
  7. get_node_metadata for an unknown host returns only base fields.
  8. decommission_node removes the node from the registry.
  9. discover_nodes after decommissioning returns an empty list.
 10. decommission_node on an unknown host returns False.
 11. Multiple nodes can coexist with distinct IPs.
 12. Adapter configuration is reflected in returned metadata.
"""

import pytest

from chimera.infrastructure.adapters.aws_adapter import AWSAdapter
from chimera.infrastructure.adapters.gcp_adapter import GCPAdapter
from chimera.infrastructure.adapters.azure_adapter import AzureAdapter
from chimera.domain.value_objects.node import Node
from chimera.domain.ports.cloud_provider_port import CloudProviderPort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_aws(**kwargs) -> AWSAdapter:
    """Return an AWSAdapter pre-configured for tests."""
    defaults = dict(
        region="eu-west-1",
        default_ami="ami-0test1234567890ab",
        default_subnet_id="subnet-test0001",
        default_security_group_ids=["sg-test0001"],
        default_key_name="chimera-key",
        ssh_user="ec2-user",
        ssh_port=22,
    )
    defaults.update(kwargs)
    return AWSAdapter(**defaults)


def _make_gcp(**kwargs) -> GCPAdapter:
    """Return a GCPAdapter pre-configured for tests."""
    defaults = dict(
        project="chimera-test-project",
        zone="europe-west1-b",
        default_machine_type="e2-micro",
        ssh_user="ubuntu",
        ssh_port=22,
    )
    defaults.update(kwargs)
    return GCPAdapter(**defaults)


def _make_azure(**kwargs) -> AzureAdapter:
    """Return an AzureAdapter pre-configured for tests."""
    defaults = dict(
        subscription_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        resource_group="chimera-test-rg",
        location="westeurope",
        default_vm_size="Standard_B1s",
        ssh_user="azureuser",
        ssh_port=22,
    )
    defaults.update(kwargs)
    return AzureAdapter(**defaults)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestCloudProviderPortConformance:
    """Verify that all adapters satisfy the CloudProviderPort Protocol."""

    def test_aws_satisfies_protocol(self):
        assert isinstance(_make_aws(), CloudProviderPort)

    def test_gcp_satisfies_protocol(self):
        assert isinstance(_make_gcp(), CloudProviderPort)

    def test_azure_satisfies_protocol(self):
        assert isinstance(_make_azure(), CloudProviderPort)


# ---------------------------------------------------------------------------
# AWS adapter tests
# ---------------------------------------------------------------------------

class TestAWSAdapter:

    @pytest.mark.asyncio
    async def test_discover_empty_registry(self):
        adapter = _make_aws()
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_provision_returns_node(self):
        adapter = _make_aws()
        node = await adapter.provision_node("web-01", instance_type="t3.micro")
        assert isinstance(node, Node)
        assert node.user == "ec2-user"
        assert node.port == 22
        # Private IP should be a valid non-empty string
        assert node.host

    @pytest.mark.asyncio
    async def test_provision_registers_in_discovery(self):
        adapter = _make_aws()
        node = await adapter.provision_node("web-01")
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_discover_with_matching_name_filter(self):
        adapter = _make_aws()
        node = await adapter.provision_node("web-01")
        nodes = await adapter.discover_nodes(filters={"Name": "web-01"})
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_discover_with_nonmatching_filter_excludes_node(self):
        adapter = _make_aws()
        await adapter.provision_node("web-01")
        nodes = await adapter.discover_nodes(filters={"Name": "db-01"})
        assert nodes == []

    @pytest.mark.asyncio
    async def test_get_metadata_enriched_for_provisioned_node(self):
        adapter = _make_aws()
        node = await adapter.provision_node("web-01", instance_type="t3.small")
        meta = await adapter.get_node_metadata(node)

        assert meta["provider"] == "aws"
        assert meta["host"] == node.host
        assert meta["region"] == "eu-west-1"
        assert meta["instance_type"] == "t3.small"
        assert meta["state"] == "running"
        assert meta["image_id"] == "ami-0test1234567890ab"
        assert meta["tags"]["Name"] == "web-01"
        assert meta["tags"]["ManagedBy"] == "chimera"
        assert "instance_id" in meta
        assert meta["instance_id"].startswith("i-")

    @pytest.mark.asyncio
    async def test_get_metadata_base_fields_for_unknown_host(self):
        adapter = _make_aws()
        node = Node(host="10.9.9.9", user="ec2-user")
        meta = await adapter.get_node_metadata(node)
        assert meta["provider"] == "aws"
        assert meta["host"] == "10.9.9.9"
        assert "instance_id" not in meta

    @pytest.mark.asyncio
    async def test_decommission_returns_true_and_removes_from_registry(self):
        adapter = _make_aws()
        node = await adapter.provision_node("web-01")
        result = await adapter.decommission_node(node)
        assert result is True
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_decommission_unknown_host_returns_false(self):
        adapter = _make_aws()
        node = Node(host="10.9.9.9", user="ec2-user")
        result = await adapter.decommission_node(node)
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_nodes_have_distinct_ips(self):
        adapter = _make_aws()
        node_a = await adapter.provision_node("web-01")
        node_b = await adapter.provision_node("web-02")
        assert node_a.host != node_b.host
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_provision_custom_ssh_user_and_port(self):
        adapter = _make_aws()
        node = await adapter.provision_node("bastion", ssh_user="admin", ssh_port=2222)
        assert node.user == "admin"
        assert node.port == 2222

    @pytest.mark.asyncio
    async def test_provision_custom_region_override(self):
        adapter = _make_aws(region="us-east-1")
        node = await adapter.provision_node("web-01", region="ap-southeast-1")
        # Node is still returned; the region override is applied internally.
        assert isinstance(node, Node)

    @pytest.mark.asyncio
    async def test_decommission_only_removes_target_node(self):
        adapter = _make_aws()
        node_a = await adapter.provision_node("web-01")
        node_b = await adapter.provision_node("web-02")
        result = await adapter.decommission_node(node_a)
        assert result is True
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 1
        assert nodes[0].host == node_b.host

    @pytest.mark.asyncio
    async def test_metadata_includes_key_name(self):
        adapter = _make_aws(default_key_name="my-key")
        node = await adapter.provision_node("bastion")
        meta = await adapter.get_node_metadata(node)
        assert meta.get("key_name") == "my-key"

    @pytest.mark.asyncio
    async def test_metadata_includes_vpc_and_subnet(self):
        adapter = _make_aws(default_subnet_id="subnet-abc123")
        node = await adapter.provision_node("web-01")
        meta = await adapter.get_node_metadata(node)
        assert "vpc_id" in meta
        assert "subnet_id" in meta

    @pytest.mark.asyncio
    async def test_discover_managed_by_chimera_filter(self):
        adapter = _make_aws()
        node = await adapter.provision_node("web-01")
        # All provisioned nodes carry the ManagedBy=chimera tag.
        nodes = await adapter.discover_nodes(filters={"ManagedBy": "chimera"})
        assert len(nodes) == 1
        assert nodes[0].host == node.host


# ---------------------------------------------------------------------------
# GCP adapter tests
# ---------------------------------------------------------------------------

class TestGCPAdapter:

    @pytest.mark.asyncio
    async def test_discover_empty_registry(self):
        adapter = _make_gcp()
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_provision_returns_node(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("chimera-vm-1", instance_type="e2-small")
        assert isinstance(node, Node)
        assert node.user == "ubuntu"
        assert node.port == 22
        assert node.host

    @pytest.mark.asyncio
    async def test_provision_registers_in_discovery(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("chimera-vm-1")
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_discover_with_matching_label_filter(self):
        adapter = _make_gcp()
        node = await adapter.provision_node(
            "chimera-vm-1", labels={"env": "staging"}
        )
        nodes = await adapter.discover_nodes(filters={"env": "staging"})
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_discover_with_nonmatching_label_filter(self):
        adapter = _make_gcp()
        await adapter.provision_node("chimera-vm-1", labels={"env": "staging"})
        nodes = await adapter.discover_nodes(filters={"env": "production"})
        assert nodes == []

    @pytest.mark.asyncio
    async def test_get_metadata_enriched_for_provisioned_node(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("chimera-vm-1", instance_type="n2-standard-2")
        meta = await adapter.get_node_metadata(node)

        assert meta["provider"] == "gcp"
        assert meta["host"] == node.host
        assert meta["project"] == "chimera-test-project"
        assert meta["zone"] == "europe-west1-b"
        assert meta["machine_type"] == "n2-standard-2"
        assert meta["status"] == "RUNNING"
        assert meta["labels"]["managed-by"] == "chimera"
        assert "instance_id" in meta
        assert "instance_name" in meta
        assert meta["instance_name"] == "chimera-vm-1"

    @pytest.mark.asyncio
    async def test_get_metadata_base_fields_for_unknown_host(self):
        adapter = _make_gcp()
        node = Node(host="10.9.9.9", user="ubuntu")
        meta = await adapter.get_node_metadata(node)
        assert meta["provider"] == "gcp"
        assert meta["host"] == "10.9.9.9"
        assert "instance_id" not in meta

    @pytest.mark.asyncio
    async def test_decommission_returns_true_and_removes_from_registry(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("chimera-vm-1")
        result = await adapter.decommission_node(node)
        assert result is True
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_decommission_unknown_host_returns_false(self):
        adapter = _make_gcp()
        node = Node(host="10.9.9.9", user="ubuntu")
        result = await adapter.decommission_node(node)
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_nodes_have_distinct_ips(self):
        adapter = _make_gcp()
        node_a = await adapter.provision_node("vm-1")
        node_b = await adapter.provision_node("vm-2")
        assert node_a.host != node_b.host
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_provision_custom_ssh_user_and_port(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("bastion", ssh_user="ops", ssh_port=2222)
        assert node.user == "ops"
        assert node.port == 2222

    @pytest.mark.asyncio
    async def test_decommission_only_removes_target_node(self):
        adapter = _make_gcp()
        node_a = await adapter.provision_node("vm-1")
        node_b = await adapter.provision_node("vm-2")
        result = await adapter.decommission_node(node_a)
        assert result is True
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 1
        assert nodes[0].host == node_b.host

    @pytest.mark.asyncio
    async def test_metadata_includes_self_link(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("vm-1")
        meta = await adapter.get_node_metadata(node)
        assert "self_link" in meta
        assert "chimera-test-project" in meta["self_link"]

    @pytest.mark.asyncio
    async def test_managed_by_label_always_present(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("vm-1", labels={"team": "platform"})
        meta = await adapter.get_node_metadata(node)
        labels = meta["labels"]
        assert labels.get("managed-by") == "chimera"
        assert labels.get("team") == "platform"

    @pytest.mark.asyncio
    async def test_discover_managed_by_label_filter(self):
        adapter = _make_gcp()
        node = await adapter.provision_node("vm-1")
        nodes = await adapter.discover_nodes(filters={"managed-by": "chimera"})
        assert len(nodes) == 1
        assert nodes[0].host == node.host


# ---------------------------------------------------------------------------
# Azure adapter tests
# ---------------------------------------------------------------------------

class TestAzureAdapter:

    @pytest.mark.asyncio
    async def test_discover_empty_registry(self):
        adapter = _make_azure()
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_provision_returns_node(self):
        adapter = _make_azure()
        node = await adapter.provision_node("chimera-vm-1", instance_type="Standard_D2s_v3")
        assert isinstance(node, Node)
        assert node.user == "azureuser"
        assert node.port == 22
        assert node.host

    @pytest.mark.asyncio
    async def test_provision_registers_in_discovery(self):
        adapter = _make_azure()
        node = await adapter.provision_node("chimera-vm-1")
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_discover_with_matching_tag_filter(self):
        adapter = _make_azure()
        node = await adapter.provision_node(
            "chimera-vm-1", tags={"Environment": "staging"}
        )
        nodes = await adapter.discover_nodes(filters={"Environment": "staging"})
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_discover_with_nonmatching_tag_filter(self):
        adapter = _make_azure()
        await adapter.provision_node("chimera-vm-1", tags={"Environment": "staging"})
        nodes = await adapter.discover_nodes(filters={"Environment": "production"})
        assert nodes == []

    @pytest.mark.asyncio
    async def test_get_metadata_enriched_for_provisioned_node(self):
        adapter = _make_azure()
        node = await adapter.provision_node("chimera-vm-1", instance_type="Standard_D4s_v3")
        meta = await adapter.get_node_metadata(node)

        assert meta["provider"] == "azure"
        assert meta["host"] == node.host
        assert meta["subscription_id"] == "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
        assert meta["resource_group"] == "chimera-test-rg"
        assert meta["location"] == "westeurope"
        assert meta["vm_size"] == "Standard_D4s_v3"
        assert meta["provisioning_state"] == "Succeeded"
        assert meta["power_state"] == "PowerState/running"
        assert meta["tags"]["ManagedBy"] == "chimera"
        assert "vm_id" in meta
        assert "chimera-test-rg" in meta["vm_id"]
        assert "vm_name" in meta
        assert meta["vm_name"] == "chimera-vm-1"

    @pytest.mark.asyncio
    async def test_get_metadata_base_fields_for_unknown_host(self):
        adapter = _make_azure()
        node = Node(host="172.16.9.9", user="azureuser")
        meta = await adapter.get_node_metadata(node)
        assert meta["provider"] == "azure"
        assert meta["host"] == "172.16.9.9"
        assert "vm_id" not in meta

    @pytest.mark.asyncio
    async def test_decommission_returns_true_and_removes_from_registry(self):
        adapter = _make_azure()
        node = await adapter.provision_node("chimera-vm-1")
        result = await adapter.decommission_node(node)
        assert result is True
        nodes = await adapter.discover_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_decommission_unknown_host_returns_false(self):
        adapter = _make_azure()
        node = Node(host="172.16.9.9", user="azureuser")
        result = await adapter.decommission_node(node)
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_nodes_have_distinct_ips(self):
        adapter = _make_azure()
        node_a = await adapter.provision_node("vm-1")
        node_b = await adapter.provision_node("vm-2")
        assert node_a.host != node_b.host
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_provision_custom_ssh_user_and_port(self):
        adapter = _make_azure()
        node = await adapter.provision_node("bastion", ssh_user="ops", ssh_port=2222)
        assert node.user == "ops"
        assert node.port == 2222

    @pytest.mark.asyncio
    async def test_decommission_only_removes_target_node(self):
        adapter = _make_azure()
        node_a = await adapter.provision_node("vm-1")
        node_b = await adapter.provision_node("vm-2")
        result = await adapter.decommission_node(node_a)
        assert result is True
        nodes = await adapter.discover_nodes()
        assert len(nodes) == 1
        assert nodes[0].host == node_b.host

    @pytest.mark.asyncio
    async def test_metadata_includes_image_reference(self):
        adapter = _make_azure()
        node = await adapter.provision_node("vm-1")
        meta = await adapter.get_node_metadata(node)
        assert "image_reference" in meta
        img = meta["image_reference"]
        assert "publisher" in img
        assert "offer" in img

    @pytest.mark.asyncio
    async def test_metadata_includes_os_profile(self):
        adapter = _make_azure(default_admin_username="chimera-admin")
        node = await adapter.provision_node("vm-1")
        meta = await adapter.get_node_metadata(node)
        assert "os_profile" in meta
        assert meta["os_profile"].get("adminUsername") == "chimera-admin"

    @pytest.mark.asyncio
    async def test_managed_by_tag_always_present(self):
        adapter = _make_azure()
        node = await adapter.provision_node("vm-1", tags={"Team": "platform"})
        meta = await adapter.get_node_metadata(node)
        tags = meta["tags"]
        assert tags.get("ManagedBy") == "chimera"
        assert tags.get("Team") == "platform"

    @pytest.mark.asyncio
    async def test_discover_managed_by_chimera_filter(self):
        adapter = _make_azure()
        node = await adapter.provision_node("vm-1")
        nodes = await adapter.discover_nodes(filters={"ManagedBy": "chimera"})
        assert len(nodes) == 1
        assert nodes[0].host == node.host

    @pytest.mark.asyncio
    async def test_provision_location_override(self):
        adapter = _make_azure(location="eastus")
        node = await adapter.provision_node("vm-1", region="northeurope")
        assert isinstance(node, Node)
