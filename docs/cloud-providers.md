# Cloud Provider Guide

## Overview

Chimera supports multi-cloud infrastructure through the `CloudProviderPort` protocol. This abstraction allows Chimera to discover, provision, and decommission nodes across AWS, GCP, and Azure using a unified interface, while each provider adapter handles cloud-specific API interactions.

## CloudProviderPort Interface

All cloud provider adapters implement the same protocol:

```python
class CloudProviderPort(Protocol):
    async def discover_nodes(self, filters: Optional[dict[str, str]] = None) -> list[Node]
    async def provision_node(self, name: str, instance_type: str = "t3.micro",
                             region: str = "us-east-1", **kwargs) -> Node
    async def decommission_node(self, node: Node) -> bool
    async def get_node_metadata(self, node: Node) -> dict[str, Any]
```

| Method              | Description                                              |
|---------------------|----------------------------------------------------------|
| `discover_nodes`    | Find existing nodes matching optional tag/label filters  |
| `provision_node`    | Create a new node and return its connection details      |
| `decommission_node` | Terminate a node; returns `True` on success              |
| `get_node_metadata` | Retrieve cloud-specific metadata for a node              |

The `Node` value object returned by these methods contains the host address and connection details that Chimera uses for deployment and drift detection.

## Supported Providers

### Amazon Web Services (AWS)

#### Prerequisites

- AWS credentials configured via `~/.aws/credentials`, environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), or IAM role
- Appropriate IAM permissions for EC2 operations

#### Configuration

Set the following in `chimera.json` or via environment variables:

```json
{
  "fleet": {
    "targets": ["root@10.0.0.1:22", "root@10.0.0.2:22"]
  }
}
```

Or use the cloud provider adapter for dynamic discovery:

```bash
export AWS_DEFAULT_REGION=us-east-1
```

#### Node Discovery

The AWS adapter discovers EC2 instances using tag-based filters:

```python
nodes = await aws_provider.discover_nodes(filters={
    "tag:chimera-managed": "true",
    "instance-state-name": "running",
})
```

Common filter keys:
- `tag:<key>` -- Filter by EC2 tag
- `instance-state-name` -- Filter by state (`running`, `stopped`, etc.)
- `instance-type` -- Filter by instance type
- `vpc-id` -- Filter by VPC

#### Auto-Scaling Integration

Chimera integrates with AWS Auto Scaling Groups by discovering new instances as they launch. The autonomous watch loop (`chimera watch`) continuously polls for fleet membership changes. When new instances join the ASG:

1. `discover_nodes` picks up the new instance
2. The drift detection service checks the new node against the expected Nix hash
3. If the node is not yet configured, a deployment is triggered automatically
4. If the node drifts later, the healing pipeline handles remediation

#### Provisioning

```python
node = await aws_provider.provision_node(
    name="chimera-node-03",
    instance_type="t3.medium",
    region="us-west-2",
    ami_id="ami-0123456789abcdef0",
    subnet_id="subnet-abc123",
    security_groups=["sg-xyz789"],
)
```

### Google Cloud Platform (GCP)

#### Prerequisites

- GCP credentials configured via `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to a service account key, or via default application credentials
- Appropriate IAM roles for Compute Engine operations

#### Configuration

```json
{
  "fleet": {
    "targets": ["root@10.128.0.2:22", "root@10.128.0.3:22"]
  }
}
```

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GCP_PROJECT=my-project-id
export GCP_ZONE=us-central1-a
```

#### Node Discovery

The GCP adapter discovers Compute Engine instances using label-based filters:

```python
nodes = await gcp_provider.discover_nodes(filters={
    "labels.chimera-managed": "true",
    "status": "RUNNING",
})
```

Common filter keys:
- `labels.<key>` -- Filter by instance label
- `status` -- Filter by state (`RUNNING`, `TERMINATED`, etc.)
- `machineType` -- Filter by machine type
- `zone` -- Filter by zone

#### Auto-Scaling Integration

Chimera works with GCP Managed Instance Groups (MIGs). The discovery mechanism detects new instances added by the autoscaler, and the autonomous loop ensures they converge to the expected configuration.

#### Provisioning

```python
node = await gcp_provider.provision_node(
    name="chimera-node-03",
    instance_type="e2-medium",
    region="us-central1-a",
    image_family="nixos-24-05",
    network="default",
    subnet="default",
)
```

### Microsoft Azure

#### Prerequisites

- Azure credentials configured via environment variables (`AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`), managed identity, or Azure CLI login
- Appropriate RBAC roles for Virtual Machine operations

#### Configuration

```json
{
  "fleet": {
    "targets": ["root@10.0.1.4:22", "root@10.0.1.5:22"]
  }
}
```

```bash
export AZURE_SUBSCRIPTION_ID=00000000-0000-0000-0000-000000000000
export AZURE_RESOURCE_GROUP=chimera-fleet
```

#### Node Discovery

The Azure adapter discovers Virtual Machines using tag-based filters:

```python
nodes = await azure_provider.discover_nodes(filters={
    "tag:chimera-managed": "true",
    "powerState": "VM running",
})
```

Common filter keys:
- `tag:<key>` -- Filter by VM tag
- `powerState` -- Filter by power state
- `vmSize` -- Filter by VM size
- `resourceGroup` -- Filter by resource group

#### Auto-Scaling Integration

Chimera integrates with Azure Virtual Machine Scale Sets (VMSS). When the scale set adds instances, Chimera discovers them and ensures configuration convergence through the standard drift detection pipeline.

#### Provisioning

```python
node = await azure_provider.provision_node(
    name="chimera-node-03",
    instance_type="Standard_B2s",
    region="eastus",
    resource_group="chimera-fleet",
    image_reference="nixos:latest",
    vnet="chimera-vnet",
    subnet="default",
)
```

## Node Discovery Workflow

Regardless of cloud provider, the node discovery workflow follows the same pattern:

```
1. chimera watch (or deploy) starts
2. Cloud provider adapter calls discover_nodes() with filters
3. Returned Node objects are added to the fleet target list
4. For each node:
   a. Nix hash is built from the expected configuration
   b. Current hash is fetched from the node via RemoteExecutorPort
   c. Hashes are compared (congruence check)
   d. If drift is detected, severity is assessed and healing is triggered
5. Loop repeats at the configured interval
```

## Static vs Dynamic Targets

Chimera supports two approaches to fleet management:

**Static targets** -- Nodes listed explicitly in the config file or CLI `--targets` flag. Suitable for small, stable fleets.

```bash
chimera deploy -t root@10.0.0.1:22,root@10.0.0.2:22 "nixos-rebuild switch"
```

**Dynamic targets** -- Nodes discovered at runtime through cloud provider adapters. Suitable for auto-scaling environments where fleet membership changes over time. The `discover_nodes` method is called periodically to refresh the target list.

Both approaches can be combined: static targets serve as a baseline, and dynamic discovery adds ephemeral nodes.
