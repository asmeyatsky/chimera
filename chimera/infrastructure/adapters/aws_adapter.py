"""
AWS Cloud Provider Adapter

Architectural Intent:
- Implements CloudProviderPort for AWS EC2
- Simulates boto3 SDK call patterns without importing the real SDK, enabling
  integration testing and local development with zero cloud credentials
- When the real boto3 library is available, replace the _stub_* helpers with
  actual boto3.client("ec2") calls; the public method signatures remain stable

Design Decisions:
- __init__ accepts all provider configuration (region, credentials profile,
  VPC/subnet defaults) so the adapter is fully self-contained and testable
- Every simulated API call is logged at DEBUG level with the request payload,
  mirroring the structure of boto3 response dictionaries exactly
- discover_nodes translates EC2 Reservation/Instance dicts into Node value
  objects, filtering by tag Name=Value pairs when filters are provided
- provision_node simulates the RunInstances response and returns a Node whose
  host is the simulated private IP address
- decommission_node simulates TerminateInstances and returns True on success
- get_node_metadata returns the full instance dict for the given node's IP,
  keyed by the fields callers most commonly inspect

Simulated AWS region defaults: us-east-1
Simulated AMI: ami-0abcdef1234567890 (placeholder)
"""

import logging
import uuid
import datetime
from typing import Optional, Any

from chimera.domain.value_objects.node import Node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers that mimic the shape of real boto3 response payloads.
# Replace these with actual boto3 client calls when SDK credentials are
# available.
# ---------------------------------------------------------------------------

def _make_instance_id() -> str:
    """Return a plausible EC2 instance ID."""
    return "i-" + uuid.uuid4().hex[:17]


def _make_private_ip(index: int = 0) -> str:
    """Return a deterministic private IP for simulation."""
    return f"10.0.{(index // 256) % 256}.{index % 256 + 1}"


def _stub_describe_instances(
    region: str,
    filters: Optional[list[dict]] = None,
    simulated_instances: Optional[list[dict]] = None,
) -> dict:
    """
    Simulate a boto3 EC2.describe_instances() response.

    The real call looks like:
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_instances(Filters=filters or [])

    Returns a dict matching the DescribeInstances response structure:
    {
        "Reservations": [
            {
                "ReservationId": "r-...",
                "OwnerId": "123456789012",
                "Instances": [ { ...instance dict... } ]
            }
        ],
        "ResponseMetadata": { "HTTPStatusCode": 200, ... }
    }
    """
    instances = simulated_instances or []
    reservations = []
    for inst in instances:
        reservations.append(
            {
                "ReservationId": "r-" + uuid.uuid4().hex[:17],
                "OwnerId": "123456789012",
                "Instances": [inst],
            }
        )
    return {
        "Reservations": reservations,
        "ResponseMetadata": {
            "RequestId": str(uuid.uuid4()),
            "HTTPStatusCode": 200,
            "HTTPHeaders": {},
        },
    }


def _stub_run_instances(
    region: str,
    image_id: str,
    instance_type: str,
    name: str,
    subnet_id: Optional[str],
    security_group_ids: list[str],
    key_name: Optional[str],
    user_data: Optional[str],
    private_ip: str,
) -> dict:
    """
    Simulate a boto3 EC2.run_instances() response.

    The real call looks like:
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.run_instances(
            ImageId=image_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            SubnetId=subnet_id,
            SecurityGroupIds=security_group_ids,
            KeyName=key_name,
            UserData=user_data or "",
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": name}]
            }]
        )

    Returns a dict matching the RunInstances response structure.
    """
    instance_id = _make_instance_id()
    now = datetime.datetime.now(datetime.UTC).isoformat()
    return {
        "Instances": [
            {
                "InstanceId": instance_id,
                "InstanceType": instance_type,
                "ImageId": image_id,
                "State": {"Code": 0, "Name": "pending"},
                "PrivateIpAddress": private_ip,
                "PublicIpAddress": None,
                "SubnetId": subnet_id or "subnet-00000000",
                "VpcId": "vpc-00000000",
                "SecurityGroups": [
                    {"GroupId": sg, "GroupName": "chimera-sg"}
                    for sg in security_group_ids
                ],
                "KeyName": key_name,
                "LaunchTime": now,
                "Placement": {"AvailabilityZone": f"{region}a"},
                "Tags": [{"Key": "Name", "Value": name}, {"Key": "ManagedBy", "Value": "chimera"}],
                "Architecture": "x86_64",
                "RootDeviceType": "ebs",
                "Hypervisor": "xen",
                "VirtualizationType": "hvm",
            }
        ],
        "ResponseMetadata": {
            "RequestId": str(uuid.uuid4()),
            "HTTPStatusCode": 200,
            "HTTPHeaders": {},
        },
    }


def _stub_terminate_instances(
    region: str,
    instance_ids: list[str],
) -> dict:
    """
    Simulate a boto3 EC2.terminate_instances() response.

    The real call looks like:
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.terminate_instances(InstanceIds=instance_ids)
    """
    return {
        "TerminatingInstances": [
            {
                "InstanceId": iid,
                "CurrentState": {"Code": 32, "Name": "shutting-down"},
                "PreviousState": {"Code": 16, "Name": "running"},
            }
            for iid in instance_ids
        ],
        "ResponseMetadata": {
            "RequestId": str(uuid.uuid4()),
            "HTTPStatusCode": 200,
            "HTTPHeaders": {},
        },
    }


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------

class AWSAdapter:
    """
    AWS EC2 cloud provider adapter.

    Simulates boto3 SDK call patterns so the adapter can be exercised in tests
    and local development without AWS credentials.  The in-memory instance
    registry (_instances) plays the role of the EC2 backend: provision_node
    adds entries and decommission_node removes them.

    Configuration parameters
    ------------------------
    region : str
        AWS region name (e.g. "us-east-1").
    profile : str | None
        AWS credentials profile name passed to boto3.Session.  Ignored in
        stub mode.
    default_ami : str
        AMI ID used when the caller does not supply one via kwargs.
    default_subnet_id : str | None
        Subnet in which new instances are launched.
    default_security_group_ids : list[str]
        Security groups attached to new instances.
    default_key_name : str | None
        EC2 key-pair name injected into new instances for SSH access.
    ssh_user : str
        Linux username used when constructing Node objects (default: "ec2-user").
    ssh_port : int
        SSH port used when constructing Node objects (default: 22).
    """

    def __init__(
        self,
        region: str = "us-east-1",
        profile: Optional[str] = None,
        default_ami: str = "ami-0abcdef1234567890",
        default_subnet_id: Optional[str] = None,
        default_security_group_ids: Optional[list[str]] = None,
        default_key_name: Optional[str] = None,
        ssh_user: str = "ec2-user",
        ssh_port: int = 22,
    ) -> None:
        self.region = region
        self.profile = profile
        self.default_ami = default_ami
        self.default_subnet_id = default_subnet_id
        self.default_security_group_ids = default_security_group_ids or ["sg-00000000"]
        self.default_key_name = default_key_name
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port

        # In-memory registry keyed by private IP address.
        # Value is the raw instance dict returned by _stub_run_instances.
        self._instances: dict[str, dict] = {}

        logger.debug(
            "AWSAdapter initialised (region=%s, profile=%s, ami=%s)",
            region,
            profile,
            default_ami,
        )

    # ------------------------------------------------------------------
    # CloudProviderPort implementation
    # ------------------------------------------------------------------

    async def discover_nodes(
        self, filters: Optional[dict[str, str]] = None
    ) -> list[Node]:
        """
        Discover EC2 instances in the configured region.

        Simulates EC2.describe_instances with optional tag-based filters.
        In the real implementation the filter dict {"Name": "value"} is
        translated to the EC2 Filters format:
            [{"Name": "tag:Name", "Values": ["value"]}]

        Parameters
        ----------
        filters : dict[str, str] | None
            Simple key=value tag filters.  Instances that do not match ALL
            provided filters are excluded from the result.

        Returns
        -------
        list[Node]
            One Node per matching running instance, using the instance's
            private IP address as the host.
        """
        logger.info(
            "AWS EC2 describe_instances (region=%s, filters=%s)",
            self.region,
            filters,
        )

        ec2_filters: list[dict] = []
        if filters:
            for tag_key, tag_value in filters.items():
                ec2_filters.append(
                    {"Name": f"tag:{tag_key}", "Values": [tag_value]}
                )

        # Build the simulated response from the in-memory registry.
        running_instances = [
            inst
            for inst in self._instances.values()
            if inst.get("State", {}).get("Name") == "running"
        ]

        response = _stub_describe_instances(
            region=self.region,
            filters=ec2_filters or None,
            simulated_instances=running_instances,
        )

        logger.debug(
            "describe_instances returned %d reservation(s)",
            len(response["Reservations"]),
        )

        nodes: list[Node] = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                # Apply tag filters locally (mirrors what EC2 does server-side).
                if filters:
                    tags = {
                        t["Key"]: t["Value"]
                        for t in instance.get("Tags", [])
                    }
                    if not all(tags.get(k) == v for k, v in filters.items()):
                        logger.debug(
                            "Skipping instance %s: tag mismatch",
                            instance["InstanceId"],
                        )
                        continue

                private_ip = instance.get("PrivateIpAddress")
                if not private_ip:
                    logger.warning(
                        "Instance %s has no PrivateIpAddress, skipping",
                        instance["InstanceId"],
                    )
                    continue

                node = Node(
                    host=private_ip,
                    user=self.ssh_user,
                    port=self.ssh_port,
                )
                logger.debug(
                    "Discovered node: %s (instance_id=%s)",
                    node,
                    instance["InstanceId"],
                )
                nodes.append(node)

        logger.info("discover_nodes found %d node(s)", len(nodes))
        return nodes

    async def provision_node(
        self,
        name: str,
        instance_type: str = "t3.micro",
        region: Optional[str] = None,
        **kwargs: Any,
    ) -> Node:
        """
        Provision a new EC2 instance and return its Node.

        Simulates EC2.run_instances.  The instance transitions immediately to
        the "running" state in the in-memory registry so it appears in
        subsequent discover_nodes calls.

        Parameters
        ----------
        name : str
            Value applied to the EC2 "Name" tag.
        instance_type : str
            EC2 instance type (e.g. "t3.micro", "m5.large").
        region : str | None
            Override the adapter's default region for this call.
        **kwargs
            ami : str          — Override the default AMI ID.
            subnet_id : str    — Override the default subnet.
            security_group_ids : list[str]
            key_name : str
            user_data : str    — Base64-encoded cloud-init script.
            ssh_user : str     — Override the SSH username for the Node.
            ssh_port : int     — Override the SSH port for the Node.

        Returns
        -------
        Node
            A Node whose host is the newly provisioned instance's private IP.
        """
        effective_region = region or self.region
        image_id = kwargs.get("ami", self.default_ami)
        subnet_id = kwargs.get("subnet_id", self.default_subnet_id)
        security_group_ids = kwargs.get(
            "security_group_ids", self.default_security_group_ids
        )
        key_name = kwargs.get("key_name", self.default_key_name)
        user_data = kwargs.get("user_data")
        ssh_user = kwargs.get("ssh_user", self.ssh_user)
        ssh_port = kwargs.get("ssh_port", self.ssh_port)

        private_ip = _make_private_ip(len(self._instances))

        logger.info(
            "AWS EC2 run_instances: name=%s type=%s region=%s ami=%s ip=%s",
            name,
            instance_type,
            effective_region,
            image_id,
            private_ip,
        )

        response = _stub_run_instances(
            region=effective_region,
            image_id=image_id,
            instance_type=instance_type,
            name=name,
            subnet_id=subnet_id,
            security_group_ids=security_group_ids,
            key_name=key_name,
            user_data=user_data,
            private_ip=private_ip,
        )

        instance = response["Instances"][0]
        # Simulate the instance reaching "running" state.
        instance["State"] = {"Code": 16, "Name": "running"}
        self._instances[private_ip] = instance

        logger.info(
            "Provisioned EC2 instance %s at %s",
            instance["InstanceId"],
            private_ip,
        )

        return Node(host=private_ip, user=ssh_user, port=ssh_port)

    async def decommission_node(self, node: Node) -> bool:
        """
        Terminate the EC2 instance backing the given Node.

        Simulates EC2.terminate_instances using the node's host (private IP)
        to look up the instance ID in the in-memory registry.

        Parameters
        ----------
        node : Node
            The node to decommission.  The host field must match the private
            IP of a previously provisioned instance.

        Returns
        -------
        bool
            True if the instance was found and successfully terminated.
        """
        instance = self._instances.get(node.host)
        if instance is None:
            logger.warning(
                "decommission_node: no instance found for host %s", node.host
            )
            return False

        instance_id = instance["InstanceId"]
        logger.info(
            "AWS EC2 terminate_instances: instance_id=%s host=%s",
            instance_id,
            node.host,
        )

        response = _stub_terminate_instances(
            region=self.region,
            instance_ids=[instance_id],
        )

        terminating = response.get("TerminatingInstances", [])
        if terminating and terminating[0]["CurrentState"]["Name"] == "shutting-down":
            del self._instances[node.host]
            logger.info("Instance %s successfully terminated", instance_id)
            return True

        logger.error(
            "Unexpected termination response for instance %s: %s",
            instance_id,
            terminating,
        )
        return False

    async def get_node_metadata(self, node: Node) -> dict[str, Any]:
        """
        Return EC2 instance metadata for the given Node.

        Looks up the instance in the in-memory registry by private IP.  If the
        host has not been provisioned via this adapter the method returns a
        minimal dict so callers can still inspect the provider field.

        Parameters
        ----------
        node : Node
            The node whose metadata is requested.

        Returns
        -------
        dict[str, Any]
            A dict that always contains at minimum:
                provider        : "aws"
                host            : node.host
                region          : configured region
            When the instance exists in the registry it additionally contains:
                instance_id     : str
                instance_type   : str
                image_id        : str
                state           : str  ("running" | "stopped" | ...)
                availability_zone : str
                tags            : dict[str, str]
                launch_time     : str
        """
        logger.debug(
            "AWS get_node_metadata for host=%s region=%s", node.host, self.region
        )

        base: dict[str, Any] = {
            "provider": "aws",
            "host": node.host,
            "region": self.region,
        }

        instance = self._instances.get(node.host)
        if instance is None:
            logger.debug("No instance record for host %s", node.host)
            return base

        tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
        base.update(
            {
                "instance_id": instance["InstanceId"],
                "instance_type": instance["InstanceType"],
                "image_id": instance["ImageId"],
                "state": instance.get("State", {}).get("Name", "unknown"),
                "availability_zone": instance.get("Placement", {}).get(
                    "AvailabilityZone", ""
                ),
                "tags": tags,
                "launch_time": instance.get("LaunchTime", ""),
                "vpc_id": instance.get("VpcId", ""),
                "subnet_id": instance.get("SubnetId", ""),
                "key_name": instance.get("KeyName"),
            }
        )
        return base
