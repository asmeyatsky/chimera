"""
Azure Cloud Provider Adapter

Architectural Intent:
- Implements CloudProviderPort for Microsoft Azure Virtual Machines
- Simulates azure-mgmt-compute SDK call patterns without importing the real
  library, enabling integration testing and local development with zero Azure
  credentials
- When azure-mgmt-compute (and azure-identity) are available, replace the
  _stub_* helpers with actual ComputeManagementClient().virtual_machines calls;
  the public method signatures remain stable

Design Decisions:
- __init__ accepts all provider configuration (subscription_id, resource_group,
  location, VM size defaults, VNet/subnet references, image reference) so the
  adapter is fully self-contained and testable
- Every simulated API call is logged at DEBUG level with the request payload,
  mirroring the structure of the Azure REST API / azure-mgmt-compute response
  objects (expressed as plain dicts here)
- discover_nodes translates VirtualMachine resource dicts into Node value
  objects, filtering by tag key=value pairs when filters are provided
- provision_node simulates VirtualMachines.begin_create_or_update() and returns
  a Node whose host is the simulated private IP from the NIC resource
- decommission_node simulates VirtualMachines.begin_delete() and NIC cleanup
- get_node_metadata returns the full VM resource dict

Simulated defaults:
  subscription : 00000000-0000-0000-0000-000000000000
  resource_group : chimera-rg
  location : eastus
  vm_size : Standard_B1s
"""

import logging
import uuid
import datetime
from typing import Optional, Any

from chimera.domain.value_objects.node import Node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers that mimic azure-mgmt-compute / Azure REST API payloads
# ---------------------------------------------------------------------------

def _make_vm_id(subscription_id: str, resource_group: str, name: str) -> str:
    return (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.Compute/virtualMachines/{name}"
    )


def _make_nic_id(subscription_id: str, resource_group: str, name: str) -> str:
    return (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.Network/networkInterfaces/{name}-nic"
    )


def _make_private_ip(index: int = 0) -> str:
    """Return a deterministic private IP for simulation."""
    return f"172.16.{(index // 256) % 256}.{index % 256 + 4}"


def _stub_virtual_machines_list(
    subscription_id: str,
    resource_group: str,
    simulated_vms: Optional[list[dict]] = None,
) -> dict:
    """
    Simulate ComputeManagementClient.virtual_machines.list() response.

    The real call looks like:
        credential = DefaultAzureCredential()
        client = ComputeManagementClient(credential, subscription_id)
        vms = list(client.virtual_machines.list(resource_group_name=resource_group))

    Returns a dict wrapping a "value" list of VM resource objects, matching
    the Azure Resource Manager list response envelope.
    """
    return {
        "value": simulated_vms or [],
        "nextLink": None,
    }


def _stub_virtual_machines_create_or_update(
    subscription_id: str,
    resource_group: str,
    location: str,
    name: str,
    vm_size: str,
    image_reference: dict,
    nic_id: str,
    admin_username: str,
    tags: dict[str, str],
    private_ip: str,
) -> dict:
    """
    Simulate ComputeManagementClient.virtual_machines.begin_create_or_update()
    LRO result.

    The real call looks like:
        client = ComputeManagementClient(credential, subscription_id)
        poller = client.virtual_machines.begin_create_or_update(
            resource_group_name=resource_group,
            vm_name=name,
            parameters=VirtualMachine(
                location=location,
                hardware_profile=HardwareProfile(vm_size=vm_size),
                storage_profile=StorageProfile(image_reference=ImageReference(**image_reference)),
                network_profile=NetworkProfile(
                    network_interfaces=[NetworkInterfaceReference(id=nic_id, primary=True)]
                ),
                os_profile=OSProfile(
                    computer_name=name,
                    admin_username=admin_username,
                    linux_configuration=LinuxConfiguration(disable_password_authentication=True),
                ),
                tags=tags,
            ),
        )
        vm = poller.result()

    Returns a dict matching the VirtualMachine resource object.
    """
    now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
    full_tags = {"ManagedBy": "chimera", **tags}
    vm_id = _make_vm_id(subscription_id, resource_group, name)
    return {
        "id": vm_id,
        "name": name,
        "type": "Microsoft.Compute/virtualMachines",
        "location": location,
        "tags": full_tags,
        "properties": {
            "vmId": str(uuid.uuid4()),
            "hardwareProfile": {"vmSize": vm_size},
            "storageProfile": {
                "imageReference": image_reference,
                "osDisk": {
                    "name": f"{name}-os-disk",
                    "createOption": "FromImage",
                    "managedDisk": {"storageAccountType": "Premium_LRS"},
                },
            },
            "networkProfile": {
                "networkInterfaces": [
                    {"id": nic_id, "properties": {"primary": True}}
                ]
            },
            "osProfile": {
                "computerName": name,
                "adminUsername": admin_username,
                "linuxConfiguration": {
                    "disablePasswordAuthentication": True,
                    "provisionVMAgent": True,
                },
            },
            "provisioningState": "Succeeded",
            "powerState": "PowerState/running",
            "timeCreated": now,
            # Internal IP stored here for convenience — in reality it is fetched
            # from the NIC resource via NetworkManagementClient.
            "_chimera_private_ip": private_ip,
        },
    }


def _stub_virtual_machines_delete(
    subscription_id: str,
    resource_group: str,
    name: str,
) -> dict:
    """
    Simulate ComputeManagementClient.virtual_machines.begin_delete() LRO result.

    The real call looks like:
        client = ComputeManagementClient(credential, subscription_id)
        poller = client.virtual_machines.begin_delete(
            resource_group_name=resource_group, vm_name=name
        )
        poller.result()

    Returns an operation status dict.
    """
    return {
        "id": f"/subscriptions/{subscription_id}/providers/Microsoft.Compute/locations/eastus/operations/{uuid.uuid4()}",
        "name": str(uuid.uuid4()),
        "status": "Succeeded",
        "startTime": datetime.datetime.now(datetime.UTC).isoformat() + "Z",
        "endTime": datetime.datetime.now(datetime.UTC).isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------

class AzureAdapter:
    """
    Azure Virtual Machines cloud provider adapter.

    Simulates azure-mgmt-compute SDK call patterns so the adapter can be
    exercised in tests and local development without Azure credentials.  The
    in-memory VM registry (_vms) plays the role of the Azure Resource Manager
    backend: provision_node adds entries and decommission_node removes them.

    Configuration parameters
    ------------------------
    subscription_id : str
        Azure subscription GUID.
    resource_group : str
        Resource group that contains all managed VMs.
    location : str
        Azure region (e.g. "eastus", "westeurope").
    default_vm_size : str
        VM SKU used when the caller does not specify one.
    default_image_reference : dict | None
        ImageReference dict (publisher, offer, sku, version).  Defaults to
        the latest Debian 12 Marketplace image.
    default_vnet : str
        Virtual network name.
    default_subnet : str
        Subnet name within the VNet.
    default_admin_username : str
        OS-level admin username (default: "azureuser").
    ssh_user : str
        Linux username used when constructing Node objects.  Often the same as
        default_admin_username.
    ssh_port : int
        SSH port used when constructing Node objects (default: 22).
    """

    _DEFAULT_IMAGE_REFERENCE = {
        "publisher": "Debian",
        "offer": "debian-12",
        "sku": "12-gen2",
        "version": "latest",
    }

    def __init__(
        self,
        subscription_id: str = "00000000-0000-0000-0000-000000000000",
        resource_group: str = "chimera-rg",
        location: str = "eastus",
        default_vm_size: str = "Standard_B1s",
        default_image_reference: Optional[dict] = None,
        default_vnet: str = "chimera-vnet",
        default_subnet: str = "default",
        default_admin_username: str = "azureuser",
        ssh_user: str = "azureuser",
        ssh_port: int = 22,
    ) -> None:
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        self.default_vm_size = default_vm_size
        self.default_image_reference = (
            default_image_reference or dict(self._DEFAULT_IMAGE_REFERENCE)
        )
        self.default_vnet = default_vnet
        self.default_subnet = default_subnet
        self.default_admin_username = default_admin_username
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port

        # In-memory registry keyed by VM name.
        # Value is the raw VM dict returned by _stub_virtual_machines_create_or_update.
        self._vms: dict[str, dict] = {}

        logger.debug(
            "AzureAdapter initialised (subscription=%s, rg=%s, location=%s, size=%s)",
            subscription_id,
            resource_group,
            location,
            default_vm_size,
        )

    # ------------------------------------------------------------------
    # CloudProviderPort implementation
    # ------------------------------------------------------------------

    async def discover_nodes(
        self, filters: Optional[dict[str, str]] = None
    ) -> list[Node]:
        """
        Discover Azure VMs in the configured resource group.

        Simulates VirtualMachinesClient.list() with optional tag-based filters.
        In the real implementation, tag filtering can be done via Azure Resource
        Graph or by post-processing the list result:
            [vm for vm in client.virtual_machines.list(resource_group)
             if all(vm.tags.get(k) == v for k, v in filters.items())]

        Parameters
        ----------
        filters : dict[str, str] | None
            Simple key=value tag filters.  VMs that do not match ALL provided
            filters are excluded from the result.

        Returns
        -------
        list[Node]
            One Node per matching running VM, using the VM's private IP
            (stored in properties._chimera_private_ip) as the host.
        """
        logger.info(
            "Azure VirtualMachines.list (subscription=%s, rg=%s, filters=%s)",
            self.subscription_id,
            self.resource_group,
            filters,
        )

        running_vms = [
            vm
            for vm in self._vms.values()
            if vm.get("properties", {}).get("powerState") == "PowerState/running"
        ]

        response = _stub_virtual_machines_list(
            subscription_id=self.subscription_id,
            resource_group=self.resource_group,
            simulated_vms=running_vms,
        )

        logger.debug(
            "VirtualMachines.list returned %d item(s)", len(response.get("value", []))
        )

        nodes: list[Node] = []
        for vm in response.get("value", []):
            if filters:
                tags = vm.get("tags", {})
                if not all(tags.get(k) == v for k, v in filters.items()):
                    logger.debug(
                        "Skipping VM %s: tag mismatch", vm.get("name", "?")
                    )
                    continue

            private_ip = vm.get("properties", {}).get("_chimera_private_ip")
            if not private_ip:
                logger.warning(
                    "VM %s has no private IP recorded, skipping",
                    vm.get("name", "?"),
                )
                continue

            node = Node(
                host=private_ip,
                user=self.ssh_user,
                port=self.ssh_port,
            )
            logger.debug("Discovered node: %s (vm=%s)", node, vm.get("name"))
            nodes.append(node)

        logger.info("discover_nodes found %d node(s)", len(nodes))
        return nodes

    async def provision_node(
        self,
        name: str,
        instance_type: str = "Standard_B1s",
        region: Optional[str] = None,
        **kwargs: Any,
    ) -> Node:
        """
        Provision a new Azure VM and return its Node.

        Simulates VirtualMachinesClient.begin_create_or_update().  The VM
        transitions immediately to PowerState/running in the in-memory registry
        so it appears in subsequent discover_nodes calls.

        Parameters
        ----------
        name : str
            VM name (must comply with Azure naming rules).
        instance_type : str
            Azure VM size (e.g. "Standard_B1s", "Standard_D4s_v3").
        region : str | None
            Override the adapter's default location for this call.
        **kwargs
            image_reference : dict     — Override the default ImageReference.
            vnet : str                 — Override the default VNet name.
            subnet : str               — Override the default subnet name.
            admin_username : str       — Override the admin OS username.
            tags : dict[str, str]      — Additional resource tags.
            ssh_user : str             — Override the SSH username for the Node.
            ssh_port : int             — Override the SSH port for the Node.

        Returns
        -------
        Node
            A Node whose host is the newly provisioned VM's private IP.
        """
        effective_location = region or self.location
        image_reference = kwargs.get("image_reference", self.default_image_reference)
        admin_username = kwargs.get("admin_username", self.default_admin_username)
        tags = kwargs.get("tags", {})
        ssh_user = kwargs.get("ssh_user", self.ssh_user)
        ssh_port = kwargs.get("ssh_port", self.ssh_port)

        private_ip = _make_private_ip(len(self._vms))
        nic_id = _make_nic_id(self.subscription_id, self.resource_group, name)

        logger.info(
            "Azure VirtualMachines.begin_create_or_update: name=%s size=%s location=%s ip=%s",
            name,
            instance_type,
            effective_location,
            private_ip,
        )

        vm = _stub_virtual_machines_create_or_update(
            subscription_id=self.subscription_id,
            resource_group=self.resource_group,
            location=effective_location,
            name=name,
            vm_size=instance_type,
            image_reference=image_reference,
            nic_id=nic_id,
            admin_username=admin_username,
            tags=tags,
            private_ip=private_ip,
        )

        self._vms[name] = vm
        logger.info(
            "Provisioned Azure VM %s (vmId=%s) at %s",
            name,
            vm["properties"]["vmId"],
            private_ip,
        )

        return Node(host=private_ip, user=ssh_user, port=ssh_port)

    async def decommission_node(self, node: Node) -> bool:
        """
        Delete the Azure VM backing the given Node.

        Simulates VirtualMachinesClient.begin_delete() using the node's host
        (private IP) to find the VM in the in-memory registry.

        Parameters
        ----------
        node : Node
            The node to decommission.  Its host field must match the private IP
            of a previously provisioned VM.

        Returns
        -------
        bool
            True if the VM was found and the delete operation succeeded.
        """
        target_name: Optional[str] = None
        for vm_name, vm in self._vms.items():
            if vm.get("properties", {}).get("_chimera_private_ip") == node.host:
                target_name = vm_name
                break

        if target_name is None:
            logger.warning(
                "decommission_node: no Azure VM found for host %s", node.host
            )
            return False

        logger.info(
            "Azure VirtualMachines.begin_delete: name=%s rg=%s host=%s",
            target_name,
            self.resource_group,
            node.host,
        )

        operation = _stub_virtual_machines_delete(
            subscription_id=self.subscription_id,
            resource_group=self.resource_group,
            name=target_name,
        )

        if operation.get("status") == "Succeeded":
            del self._vms[target_name]
            logger.info("Azure VM %s successfully deleted", target_name)
            return True

        logger.error(
            "Unexpected operation status for delete of %s: %s",
            target_name,
            operation.get("status"),
        )
        return False

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        """
        Return Azure VM metadata for the given Node.

        Looks up the VM in the in-memory registry by private IP.  If no
        matching VM is found the method returns a minimal dict so callers can
        still inspect the provider field.

        Parameters
        ----------
        node : Node
            The node whose metadata is requested.

        Returns
        -------
        dict[str, Any]
            A dict that always contains at minimum:
                provider          : "azure"
                host              : node.host
                subscription_id   : configured subscription
                resource_group    : configured resource group
                location          : configured location
            When the VM is found it additionally contains:
                vm_id             : str  (Azure resource ID path)
                vm_name           : str
                vm_size           : str
                provisioning_state : str  ("Succeeded" | ...)
                power_state       : str  ("PowerState/running" | ...)
                tags              : dict[str, str]
                image_reference   : dict
                os_profile        : dict
                time_created      : str
        """
        logger.debug(
            "Azure get_node_metadata for host=%s rg=%s",
            node.host,
            self.resource_group,
        )

        base: dict[str, Any] = {
            "provider": "azure",
            "host": node.host,
            "subscription_id": self.subscription_id,
            "resource_group": self.resource_group,
            "location": self.location,
        }

        for vm in self._vms.values():
            props = vm.get("properties", {})
            if props.get("_chimera_private_ip") == node.host:
                base.update(
                    {
                        "vm_id": vm.get("id", ""),
                        "vm_name": vm.get("name", ""),
                        "vm_size": props.get("hardwareProfile", {}).get("vmSize", ""),
                        "provisioning_state": props.get("provisioningState", ""),
                        "power_state": props.get("powerState", ""),
                        "tags": vm.get("tags", {}),
                        "image_reference": props.get("storageProfile", {}).get(
                            "imageReference", {}
                        ),
                        "os_profile": props.get("osProfile", {}),
                        "time_created": props.get("timeCreated", ""),
                    }
                )
                return base

        logger.debug("No Azure VM record for host %s", node.host)
        return base
