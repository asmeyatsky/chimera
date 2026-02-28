"""
GCP Cloud Provider Adapter

Architectural Intent:
- Implements CloudProviderPort for Google Cloud Platform Compute Engine
- Simulates google-cloud-compute SDK call patterns without importing the real
  library, enabling integration testing and local development with zero GCP
  credentials
- When google-cloud-compute is available, replace the _stub_* helpers with
  actual google.cloud.compute_v1.InstancesClient() calls; the public method
  signatures remain stable

Design Decisions:
- __init__ accepts all provider configuration (project, zone, machine type
  defaults, network/subnetwork defaults, service-account email) so the adapter
  is fully self-contained and testable
- Every simulated API call is logged at DEBUG level with the request payload,
  mirroring the structure of the GCP REST API / Compute v1 response dicts
- discover_nodes translates aggregatedList Instance dicts into Node value
  objects, filtering by label key=value pairs when filters are provided
- provision_node simulates the instances.insert operation and returns a Node
  whose host is the simulated internal IP address
- decommission_node simulates the instances.delete operation
- get_node_metadata returns the full instance resource dict

Simulated defaults:
  project : my-chimera-project
  zone    : us-central1-a
  machine : e2-micro
"""

import logging
import uuid
import datetime
from typing import Optional, Any

from chimera.domain.value_objects.node import Node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers that mimic the shape of GCP Compute Engine REST API payloads
# ---------------------------------------------------------------------------

def _make_instance_id() -> str:
    """Return a plausible GCP numeric instance ID (uint64 in the real API)."""
    return str(uuid.uuid4().int >> 64)


def _make_internal_ip(index: int = 0) -> str:
    """Return a deterministic internal IP for simulation."""
    return f"10.128.{(index // 256) % 256}.{index % 256 + 2}"


def _make_self_link(project: str, zone: str, resource: str, name: str) -> str:
    return (
        f"https://www.googleapis.com/compute/v1/projects/{project}"
        f"/zones/{zone}/{resource}/{name}"
    )


def _stub_instances_list(
    project: str,
    zone: str,
    simulated_instances: Optional[list[dict]] = None,
) -> dict:
    """
    Simulate a google.cloud.compute_v1.InstancesClient.list() response.

    The real call looks like:
        client = google.cloud.compute_v1.InstancesClient()
        request = google.cloud.compute_v1.ListInstancesRequest(
            project=project, zone=zone
        )
        page_result = client.list(request=request)

    Returns a dict matching the InstanceList resource structure:
    {
        "id": "...",
        "items": [ { ...instance resource... } ],
        "selfLink": "...",
        "kind": "compute#instanceList"
    }
    """
    items = simulated_instances or []
    return {
        "id": f"projects/{project}/zones/{zone}/instances",
        "items": items,
        "selfLink": f"https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances",
        "kind": "compute#instanceList",
    }


def _stub_instances_insert(
    project: str,
    zone: str,
    name: str,
    machine_type: str,
    image_family: str,
    network: str,
    subnetwork: Optional[str],
    service_account_email: Optional[str],
    metadata_items: list[dict],
    labels: dict[str, str],
    internal_ip: str,
) -> dict:
    """
    Simulate a google.cloud.compute_v1.InstancesClient.insert() Operation.

    The real call looks like:
        client = google.cloud.compute_v1.InstancesClient()
        instance_resource = google.cloud.compute_v1.Instance(
            name=name,
            machine_type=f"zones/{zone}/machineTypes/{machine_type}",
            disks=[...],
            network_interfaces=[...],
            labels=labels,
            metadata=google.cloud.compute_v1.Metadata(items=metadata_items),
        )
        operation = client.insert(project=project, zone=zone, instance_resource=instance_resource)
        operation.result()  # wait for completion

    Returns a dict matching the Compute Engine Instance resource.
    """
    instance_id = _make_instance_id()
    now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
    full_labels = {"managed-by": "chimera", **labels}
    return {
        "id": instance_id,
        "name": name,
        "machineType": _make_self_link(project, zone, "machineTypes", machine_type),
        "status": "RUNNING",
        "creationTimestamp": now,
        "zone": _make_self_link(project, "", "zones", zone).replace("/zones/", "/zones/"),
        "selfLink": _make_self_link(project, zone, "instances", name),
        "networkInterfaces": [
            {
                "network": f"https://www.googleapis.com/compute/v1/projects/{project}/global/networks/{network}",
                "subnetwork": (
                    f"https://www.googleapis.com/compute/v1/projects/{project}/regions/{zone[:-2]}/subnetworks/{subnetwork}"
                    if subnetwork
                    else None
                ),
                "networkIP": internal_ip,
                "accessConfigs": [],
                "kind": "compute#networkInterface",
            }
        ],
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "source": _make_self_link(project, zone, "disks", name),
                "initializeParams": {"sourceImage": image_family},
                "kind": "compute#attachedDisk",
            }
        ],
        "metadata": {"items": metadata_items, "kind": "compute#metadata"},
        "labels": full_labels,
        "serviceAccounts": (
            [{"email": service_account_email, "scopes": ["https://www.googleapis.com/auth/cloud-platform"]}]
            if service_account_email
            else []
        ),
        "kind": "compute#instance",
    }


def _stub_instances_delete(project: str, zone: str, name: str) -> dict:
    """
    Simulate a google.cloud.compute_v1.InstancesClient.delete() Operation.

    The real call looks like:
        client = google.cloud.compute_v1.InstancesClient()
        operation = client.delete(project=project, zone=zone, instance=name)
        operation.result()

    Returns an Operation dict.
    """
    return {
        "id": str(uuid.uuid4().int >> 64),
        "name": f"operation-{uuid.uuid4().hex[:8]}",
        "operationType": "delete",
        "targetLink": _make_self_link(project, zone, "instances", name),
        "status": "DONE",
        "progress": 100,
        "kind": "compute#operation",
    }


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------

class GCPAdapter:
    """
    GCP Compute Engine cloud provider adapter.

    Simulates google-cloud-compute SDK call patterns so the adapter can be
    exercised in tests and local development without GCP credentials.  The
    in-memory instance registry (_instances) plays the role of the Compute
    Engine backend: provision_node adds entries and decommission_node removes
    them.

    Configuration parameters
    ------------------------
    project : str
        GCP project ID.
    zone : str
        Default Compute Engine zone (e.g. "us-central1-a").
    default_machine_type : str
        Machine type used when the caller does not specify one.
    default_image_family : str
        Source image family for new instance boot disks.
    default_network : str
        VPC network name.
    default_subnetwork : str | None
        Subnetwork name within the VPC.
    default_service_account_email : str | None
        Service account attached to new instances.
    ssh_user : str
        Linux username used when constructing Node objects (default: "ubuntu").
    ssh_port : int
        SSH port used when constructing Node objects (default: 22).
    """

    def __init__(
        self,
        project: str = "my-chimera-project",
        zone: str = "us-central1-a",
        default_machine_type: str = "e2-micro",
        default_image_family: str = "projects/debian-cloud/global/images/family/debian-12",
        default_network: str = "default",
        default_subnetwork: Optional[str] = None,
        default_service_account_email: Optional[str] = None,
        ssh_user: str = "ubuntu",
        ssh_port: int = 22,
    ) -> None:
        self.project = project
        self.zone = zone
        self.default_machine_type = default_machine_type
        self.default_image_family = default_image_family
        self.default_network = default_network
        self.default_subnetwork = default_subnetwork
        self.default_service_account_email = default_service_account_email
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port

        # In-memory registry keyed by instance name.
        # Value is the raw instance dict returned by _stub_instances_insert.
        self._instances: dict[str, dict] = {}

        logger.debug(
            "GCPAdapter initialised (project=%s, zone=%s, machine_type=%s)",
            project,
            zone,
            default_machine_type,
        )

    # ------------------------------------------------------------------
    # CloudProviderPort implementation
    # ------------------------------------------------------------------

    async def discover_nodes(
        self, filters: Optional[dict[str, str]] = None
    ) -> list[Node]:
        """
        Discover Compute Engine instances in the configured project/zone.

        Simulates InstancesClient.list() with optional label-based filters.
        In the real implementation filters are applied as a GCE filter string:
            "labels.env=production AND labels.role=worker"

        Parameters
        ----------
        filters : dict[str, str] | None
            Simple key=value label filters.  Instances that do not match ALL
            provided filters are excluded from the result.

        Returns
        -------
        list[Node]
            One Node per matching RUNNING instance, using the instance's
            internal (networkIP) address as the host.
        """
        logger.info(
            "GCP Compute instances.list (project=%s, zone=%s, filters=%s)",
            self.project,
            self.zone,
            filters,
        )

        running_instances = [
            inst
            for inst in self._instances.values()
            if inst.get("status") == "RUNNING"
        ]

        response = _stub_instances_list(
            project=self.project,
            zone=self.zone,
            simulated_instances=running_instances,
        )

        logger.debug(
            "instances.list returned %d item(s)", len(response.get("items", []))
        )

        nodes: list[Node] = []
        for instance in response.get("items", []):
            # Apply label filters locally.
            if filters:
                labels = instance.get("labels", {})
                if not all(labels.get(k) == v for k, v in filters.items()):
                    logger.debug(
                        "Skipping instance %s: label mismatch", instance["name"]
                    )
                    continue

            network_interfaces = instance.get("networkInterfaces", [])
            if not network_interfaces:
                logger.warning(
                    "Instance %s has no networkInterfaces, skipping",
                    instance["name"],
                )
                continue

            internal_ip = network_interfaces[0].get("networkIP")
            if not internal_ip:
                logger.warning(
                    "Instance %s has no networkIP, skipping", instance["name"]
                )
                continue

            node = Node(
                host=internal_ip,
                user=self.ssh_user,
                port=self.ssh_port,
            )
            logger.debug(
                "Discovered node: %s (instance=%s)", node, instance["name"]
            )
            nodes.append(node)

        logger.info("discover_nodes found %d node(s)", len(nodes))
        return nodes

    async def provision_node(
        self,
        name: str,
        instance_type: str = "e2-micro",
        region: Optional[str] = None,
        **kwargs: Any,
    ) -> Node:
        """
        Provision a new Compute Engine instance and return its Node.

        Simulates InstancesClient.insert().  The instance transitions
        immediately to RUNNING in the in-memory registry so it appears in
        subsequent discover_nodes calls.

        Parameters
        ----------
        name : str
            Instance name (must be unique within the project/zone).
        instance_type : str
            GCE machine type (e.g. "e2-micro", "n2-standard-4").
        region : str | None
            Unused — GCE instances are zonal; set zone in __init__.
        **kwargs
            zone : str              — Override the default zone.
            image_family : str      — Override the default image family.
            network : str           — Override the default VPC network.
            subnetwork : str | None — Override the default subnetwork.
            service_account : str   — Override the default service account email.
            metadata : dict[str,str]— Key/value pairs for instance metadata.
            labels : dict[str,str]  — Key/value label pairs.
            ssh_user : str          — Override the SSH username for the Node.
            ssh_port : int          — Override the SSH port for the Node.

        Returns
        -------
        Node
            A Node whose host is the newly provisioned instance's internal IP.
        """
        zone = kwargs.get("zone", self.zone)
        image_family = kwargs.get("image_family", self.default_image_family)
        network = kwargs.get("network", self.default_network)
        subnetwork = kwargs.get("subnetwork", self.default_subnetwork)
        service_account = kwargs.get("service_account", self.default_service_account_email)
        raw_metadata = kwargs.get("metadata", {})
        labels = kwargs.get("labels", {})
        ssh_user = kwargs.get("ssh_user", self.ssh_user)
        ssh_port = kwargs.get("ssh_port", self.ssh_port)

        metadata_items = [
            {"key": k, "value": v} for k, v in raw_metadata.items()
        ]
        internal_ip = _make_internal_ip(len(self._instances))

        logger.info(
            "GCP Compute instances.insert: name=%s type=%s zone=%s ip=%s",
            name,
            instance_type,
            zone,
            internal_ip,
        )

        instance = _stub_instances_insert(
            project=self.project,
            zone=zone,
            name=name,
            machine_type=instance_type,
            image_family=image_family,
            network=network,
            subnetwork=subnetwork,
            service_account_email=service_account,
            metadata_items=metadata_items,
            labels=labels,
            internal_ip=internal_ip,
        )

        self._instances[name] = instance
        logger.info(
            "Provisioned GCE instance %s (id=%s) at %s",
            name,
            instance["id"],
            internal_ip,
        )

        return Node(host=internal_ip, user=ssh_user, port=ssh_port)

    async def decommission_node(self, node: Node) -> bool:
        """
        Delete the Compute Engine instance backing the given Node.

        Simulates InstancesClient.delete() using the node's host (internal IP)
        to find the instance in the in-memory registry.

        Parameters
        ----------
        node : Node
            The node to decommission.  Its host field must match the internal
            IP of a previously provisioned instance.

        Returns
        -------
        bool
            True if the instance was found and the delete operation succeeded.
        """
        # Find by internal IP.
        target_name: Optional[str] = None
        for inst_name, inst in self._instances.items():
            nics = inst.get("networkInterfaces", [])
            if nics and nics[0].get("networkIP") == node.host:
                target_name = inst_name
                break

        if target_name is None:
            logger.warning(
                "decommission_node: no GCE instance found for host %s", node.host
            )
            return False

        logger.info(
            "GCP Compute instances.delete: name=%s zone=%s host=%s",
            target_name,
            self.zone,
            node.host,
        )

        operation = _stub_instances_delete(
            project=self.project,
            zone=self.zone,
            name=target_name,
        )

        if operation.get("status") == "DONE":
            del self._instances[target_name]
            logger.info("GCE instance %s successfully deleted", target_name)
            return True

        logger.error(
            "Unexpected operation status for delete of %s: %s",
            target_name,
            operation.get("status"),
        )
        return False

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        """
        Return Compute Engine instance metadata for the given Node.

        Looks up the instance in the in-memory registry by internal IP.  If
        no matching instance is found the method returns a minimal dict so
        callers can still inspect the provider field.

        Parameters
        ----------
        node : Node
            The node whose metadata is requested.

        Returns
        -------
        dict[str, Any]
            A dict that always contains at minimum:
                provider        : "gcp"
                host            : node.host
                project         : configured project
                zone            : configured zone
            When the instance is found it additionally contains:
                instance_id     : str
                instance_name   : str
                machine_type    : str  (short name, e.g. "e2-micro")
                status          : str  ("RUNNING" | "TERMINATED" | ...)
                labels          : dict[str, str]
                self_link       : str
                creation_timestamp : str
        """
        logger.debug(
            "GCP get_node_metadata for host=%s project=%s zone=%s",
            node.host,
            self.project,
            self.zone,
        )

        base: dict[str, Any] = {
            "provider": "gcp",
            "host": node.host,
            "project": self.project,
            "zone": self.zone,
        }

        # Search registry by internal IP.
        for inst in self._instances.values():
            nics = inst.get("networkInterfaces", [])
            if nics and nics[0].get("networkIP") == node.host:
                machine_type_url = inst.get("machineType", "")
                short_machine_type = machine_type_url.split("/")[-1]
                base.update(
                    {
                        "instance_id": inst["id"],
                        "instance_name": inst["name"],
                        "machine_type": short_machine_type,
                        "status": inst.get("status", "UNKNOWN"),
                        "labels": inst.get("labels", {}),
                        "self_link": inst.get("selfLink", ""),
                        "creation_timestamp": inst.get("creationTimestamp", ""),
                        "network": (nics[0].get("network", "").split("/")[-1]),
                        "subnetwork": (
                            nics[0].get("subnetwork", "").split("/")[-1]
                            if nics[0].get("subnetwork")
                            else None
                        ),
                    }
                )
                return base

        logger.debug("No GCE instance record for host %s", node.host)
        return base
