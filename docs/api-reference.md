# Chimera API Reference

## CLI Commands

The `chimera` CLI is the primary entry point for all operations. Global flags apply to every command.

### Global Flags

| Flag            | Description                                  |
|-----------------|----------------------------------------------|
| `--verbose, -v` | Enable verbose output (log level: INFO)     |
| `--debug`       | Enable debug output with full tracebacks    |

### `chimera run`

Run a command in a persistent Nix+Tmux environment.

```
chimera run [--config PATH] [--session NAME] COMMAND
```

| Argument/Flag     | Required | Default           | Description                    |
|--------------------|----------|-------------------|--------------------------------|
| `script_cmd`       | Yes      |                   | Command to run                 |
| `--config, -c`     | No       | `default.nix`    | Path to Nix config file        |
| `--session, -s`    | No       | `chimera-default` | Tmux session name             |

### `chimera attach`

Attach to a running Chimera session.

```
chimera attach SESSION_ID
```

| Argument     | Required | Description               |
|--------------|----------|---------------------------|
| `session_id` | Yes      | Session ID to attach to   |

### `chimera deploy`

Deploy a command to a fleet of remote nodes.

```
chimera deploy --targets TARGETS [--config PATH] [--session NAME] COMMAND
```

| Argument/Flag     | Required | Default           | Description                         |
|--------------------|----------|-------------------|-------------------------------------|
| `script_cmd`       | Yes      |                   | Command to run remotely             |
| `--targets, -t`    | Yes      |                   | Comma-separated list of targets     |
| `--config, -c`     | No       | `default.nix`    | Path to Nix config file             |
| `--session, -s`    | No       | `chimera-deploy`  | Remote session name                |

### `chimera rollback`

Roll back nodes to a previous NixOS generation.

```
chimera rollback --targets TARGETS [--generation GEN]
```

| Argument/Flag       | Required | Default    | Description                           |
|----------------------|----------|------------|---------------------------------------|
| `--targets, -t`      | Yes      |            | Comma-separated list of targets       |
| `--generation, -g`   | No       | (previous) | Specific generation to switch to      |

### `chimera watch`

Start autonomous drift detection and self-healing.

```
chimera watch --targets TARGETS [--config PATH] [--interval SEC] [--session NAME] [--once]
```

| Argument/Flag     | Required | Default          | Description                         |
|--------------------|----------|------------------|-------------------------------------|
| `--targets, -t`    | Yes      |                  | Comma-separated list of targets     |
| `--config, -c`     | No       | `default.nix`   | Path to Nix config file             |
| `--interval, -i`   | No       | `10`             | Check interval in seconds           |
| `--session, -s`    | No       | `chimera-watch`  | Session name for healing            |
| `--once`           | No       | `false`          | Run once and exit                   |

### `chimera dash`

Launch the fleet monitoring TUI dashboard.

```
chimera dash --targets TARGETS
```

| Argument/Flag   | Required | Description                      |
|------------------|----------|----------------------------------|
| `--targets, -t`  | Yes      | Comma-separated list of targets  |

### `chimera web`

Start the web-based dashboard.

```
chimera web [--port PORT] [--host HOST]
```

| Argument/Flag   | Required | Default       | Description           |
|------------------|----------|---------------|-----------------------|
| `--port, -p`     | No       | `8080`        | Web server port       |
| `--host`         | No       | `127.0.0.1`   | Web server host       |

### `chimera mcp`

Start the MCP server for AI agent interactions.

```
chimera mcp [--port PORT] [--host HOST]
```

| Argument/Flag   | Required | Default     | Description          |
|------------------|----------|-------------|----------------------|
| `--port, -p`     | No       | `8765`      | MCP server port      |
| `--host`         | No       | `localhost` | MCP server host      |

### `chimera agent`

Start the node agent daemon.

```
chimera agent --node-id ID [--heartbeat SEC] [--drift-interval SEC] [--no-auto-heal]
```

| Argument/Flag        | Required | Default | Description                        |
|-----------------------|----------|---------|------------------------------------|
| `--node-id`           | Yes      |         | Unique identifier for this node    |
| `--heartbeat`         | No       | `5`     | Heartbeat interval in seconds      |
| `--drift-interval`    | No       | `30`    | Drift check interval in seconds    |
| `--no-auto-heal`      | No       | `false` | Disable automatic healing          |

---

## MCP Tools and Resources

The MCP server (`chimera-service`) exposes deployment capabilities for AI agents.

### Tools (Write Operations)

#### `execute_deployment`

Execute a deployment to local or remote targets.

**Input Schema:**

```json
{
  "config_path": "string (required) -- Path to Nix config file",
  "command": "string (required) -- Command to run in nix-shell",
  "session_name": "string (optional, default: 'chimera') -- Tmux session name",
  "targets": "array of strings (optional) -- Target nodes, e.g. ['root@10.0.0.1:22']"
}
```

**Response:**

```json
{
  "status": "success | failed | error",
  "message": "Deployment completed",
  "targets": ["root@10.0.0.1:22"]
}
```

#### `rollback_deployment`

Roll back deployment to a previous generation.

**Input Schema:**

```json
{
  "targets": "array of strings (required) -- Target nodes to rollback",
  "generation": "string (optional) -- Specific generation to rollback to"
}
```

**Response:**

```json
{
  "status": "success | failed | error",
  "message": "Rollback completed",
  "targets": ["root@10.0.0.1:22"]
}
```

#### `check_congruence`

Check configuration congruence across fleet nodes.

**Input Schema:**

```json
{
  "targets": "array of strings (required) -- Target nodes to check",
  "config_path": "string (required) -- Path to expected Nix config"
}
```

**Response:**

```json
{
  "status": "success",
  "message": "Congruence check result",
  "targets": ["root@10.0.0.1:22"]
}
```

### Resources (Read Operations)

#### `node://health`

Get health status of all known nodes.

**Response:** JSON string with node health data.

```json
{
  "nodes": [],
  "message": "No nodes currently tracked"
}
```

#### `deployment://{session_id}`

Get deployment status by session ID.

**Response:** JSON string with deployment status.

```json
{
  "status": "unknown"
}
```

---

## Configuration Options

All configuration is defined via frozen dataclasses in `chimera/infrastructure/config.py`. Each section maps to a sub-dataclass of `ChimeraConfig`.

### Root Configuration (`ChimeraConfig`)

| Field          | Type                | Default       | Description                     |
|----------------|---------------------|---------------|---------------------------------|
| `nix`          | `NixConfig`         | (see below)   | Nix build settings              |
| `fleet`        | `FleetConfig`       | (see below)   | Fleet target settings           |
| `watch`        | `WatchConfig`       | (see below)   | Autonomous watch settings       |
| `agent`        | `AgentNodeConfig`   | (see below)   | Node agent settings             |
| `web`          | `WebConfig`         | (see below)   | Web dashboard settings          |
| `mcp`          | `MCPConfig`         | (see below)   | MCP server settings             |
| `telemetry`    | `TelemetryConfig`   | (see below)   | OpenTelemetry settings          |
| `itsm`         | `ITSMConfig`        | (see below)   | ITSM integration settings       |
| `notifications`| `NotificationsConfig`| (see below)  | Notification channel settings   |
| `log_level`    | `str`               | `"WARNING"`   | Log level                       |

### `NixConfig`

| Field         | Type  | Default        | Description             |
|---------------|-------|----------------|-------------------------|
| `config_path` | `str` | `"default.nix"` | Path to Nix config file |

### `FleetConfig`

| Field          | Type            | Default            | Description                     |
|----------------|-----------------|--------------------|---------------------------------|
| `targets`      | `tuple[str,...]`| `()`               | Fleet target addresses          |
| `session_name` | `str`           | `"chimera-deploy"` | Default session name            |

### `WatchConfig`

| Field              | Type  | Default           | Description                  |
|--------------------|-------|-------------------|------------------------------|
| `interval_seconds` | `int` | `10`              | Drift check interval         |
| `session_name`     | `str` | `"chimera-watch"` | Session name for healing     |

### `AgentNodeConfig`

| Field                  | Type   | Default | Description                    |
|------------------------|--------|---------|--------------------------------|
| `node_id`              | `str`  | `""`    | Unique node identifier         |
| `heartbeat_interval`   | `int`  | `5`     | Heartbeat interval (seconds)   |
| `drift_check_interval` | `int`  | `30`    | Drift check interval (seconds) |
| `auto_heal`            | `bool` | `true`  | Enable automatic healing       |

### `WebConfig`

| Field  | Type  | Default       | Description          |
|--------|-------|---------------|----------------------|
| `host` | `str` | `"127.0.0.1"` | Web server bind host |
| `port` | `int` | `8080`        | Web server port      |

### `MCPConfig`

| Field  | Type  | Default       | Description          |
|--------|-------|---------------|----------------------|
| `host` | `str` | `"localhost"` | MCP server host      |
| `port` | `int` | `8765`        | MCP server port      |

### `TelemetryConfig`

| Field      | Type   | Default | Description                          |
|------------|--------|---------|--------------------------------------|
| `endpoint` | `str`  | `""`    | OpenTelemetry collector endpoint     |
| `insecure` | `bool` | `false` | Use insecure (non-TLS) connection    |

### `ITSMConfig`

| Field         | Type  | Default | Description                                    |
|---------------|-------|---------|------------------------------------------------|
| `provider`    | `str` | `""`    | ITSM provider (`"servicenow"` or `"jira"`)    |
| `url`         | `str` | `""`    | ITSM instance URL                              |
| `username`    | `str` | `""`    | API username                                   |
| `api_key`     | `str` | `""`    | API key or token                               |
| `project_key` | `str` | `""`    | Project key (for Jira)                         |

### `NotificationsConfig`

| Field                | Type  | Default | Description                   |
|----------------------|-------|---------|-------------------------------|
| `slack_webhook_url`  | `str` | `""`    | Slack incoming webhook URL    |
| `pagerduty_api_key`  | `str` | `""`    | PagerDuty API key             |
| `email_smtp_host`    | `str` | `""`    | SMTP server hostname          |
| `email_smtp_port`    | `int` | `587`   | SMTP server port              |
| `email_from`         | `str` | `""`    | Sender email address          |
| `email_to`           | `str` | `""`    | Recipient email address       |

---

## Domain Ports

All ports are defined as `Protocol` classes with `@runtime_checkable` in `chimera/domain/ports/`.

### `NixPort`

Interface for interacting with the Nix ecosystem.

```python
class NixPort(Protocol):
    async def build(self, path: str) -> NixHash
    async def instantiate(self, path: str) -> str
    async def shell(self, path: str, command: str) -> str
```

### `SessionPort`

Interface for managing persistent sessions (e.g., tmux).

```python
class SessionPort(Protocol):
    async def create_session(self, session_id: SessionId) -> bool
    async def list_sessions(self) -> list[SessionId]
    async def kill_session(self, session_id: SessionId) -> bool
    async def run_command(self, session_id: SessionId, command: str) -> bool
    async def attach_command(self, session_id: SessionId) -> str
```

### `RemoteExecutorPort`

Interface for executing commands on remote infrastructure.

```python
class RemoteExecutorPort(Protocol):
    async def sync_closure(self, nodes: list[Node], closure_path: str) -> bool
    async def exec_command(self, nodes: list[Node], command: str) -> bool
    async def get_current_hash(self, node: Node) -> Optional[NixHash]
    async def rollback(self, nodes: list[Node], generation: Optional[str] = None) -> bool
```

### `CloudProviderPort`

Interface for multi-cloud infrastructure operations.

```python
class CloudProviderPort(Protocol):
    async def discover_nodes(self, filters: Optional[dict[str, str]] = None) -> list[Node]
    async def provision_node(self, name: str, instance_type: str = "t3.micro",
                             region: str = "us-east-1", **kwargs) -> Node
    async def decommission_node(self, node: Node) -> bool
    async def get_node_metadata(self, node: Node) -> dict[str, Any]
```

### `EventBusPort`

Interface for publishing and subscribing to domain events.

```python
class EventBusPort(Protocol):
    async def publish(self, events: list[DomainEvent]) -> None
    def subscribe(self, event_type: type,
                  handler: Callable[[DomainEvent], Awaitable[None]]) -> None
```

### `OrchestratorPort`

Interface for agent-to-orchestrator communication.

```python
class OrchestratorPort(Protocol):
    async def report_health(self, health: NodeHealth) -> None
    async def report_drift(self, report: DriftReport) -> None
    async def fetch_healing_command(self, node_id: str) -> Optional[str]
    async def acknowledge_healing(self, node_id: str, success: bool) -> None
```

### `ITSMPort`

Interface for IT Service Management (incident lifecycle).

```python
class ITSMPort(Protocol):
    async def create_incident(self, title: str, description: str,
                              severity: str, node_id: str) -> str
    async def update_incident(self, ticket_id: str, status: str, comment: str) -> None
    async def resolve_incident(self, ticket_id: str, resolution: str) -> None
    async def get_incident(self, ticket_id: str) -> Optional[dict]
```

### `NotificationPort`

Interface for sending alerts and resolution notifications.

```python
class NotificationPort(Protocol):
    async def send_alert(self, title: str, message: str, severity: str,
                         node_id: str = "") -> bool
    async def send_resolution(self, title: str, message: str,
                              node_id: str = "") -> bool
```
