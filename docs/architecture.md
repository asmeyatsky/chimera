# Chimera Architecture Guide

## System Overview

Chimera is an autonomous determinism engine for self-healing infrastructure powered by Nix. It provides deterministic deployment, configuration drift detection, and automated remediation across fleets of nodes. The core guarantee is that every node in a fleet converges to the same Nix-defined configuration state, and any deviation (drift) is detected and healed automatically.

Key capabilities:

- **Deterministic deployments** via Nix closures synced to remote nodes
- **Autonomous drift detection** comparing expected vs actual Nix hashes
- **Self-healing** with severity-based remediation (restart, rebuild, rollback)
- **Fleet orchestration** deploying to multiple nodes in parallel
- **Predictive analytics** using heuristic-based risk scoring
- **Root cause analysis** correlating temporal, spatial, and deployment signals
- **SLO/SLA tracking** with error budget monitoring
- **Remediation playbooks** with marketplace-style sharing and validation
- **Policy engine** with RBAC for healing authorization
- **MCP integration** exposing deployment capabilities to AI agents

## Layer Diagram

Chimera follows a strict layered architecture inspired by Hexagonal Architecture (Ports and Adapters). Dependencies flow inward -- outer layers depend on inner layers, never the reverse.

```
+---------------------------------------------------------------+
|                     Presentation Layer                         |
|  CLI (argparse)  |  TUI (Textual)  |  Web Dashboard  |  MCP  |
+---------------------------------------------------------------+
        |                   |                |              |
        v                   v                v              v
+---------------------------------------------------------------+
|                     Application Layer                         |
|  DeployFleet | ExecuteLocalDeployment | RollbackDeployment    |
|  AutonomousLoop                                               |
+---------------------------------------------------------------+
        |                   |                |
        v                   v                v
+---------------------------------------------------------------+
|                      Domain Layer                             |
|  Entities: Deployment, NixConfig, SLO, Playbook, Policy       |
|  Services: DriftDetection, PredictiveAnalytics, RootCause,    |
|            PlaybookEngine                                      |
|  Ports: NixPort, SessionPort, RemoteExecutorPort,             |
|         CloudProviderPort, EventBusPort, OrchestratorPort,     |
|         ITSMPort, NotificationPort                             |
|  Value Objects: NixHash, Node, SessionId, CongruenceReport     |
|  Events: DomainEvent, DeploymentStarted/Completed/Failed       |
+---------------------------------------------------------------+
        ^                   ^                ^
        |                   |                |
+---------------------------------------------------------------+
|                   Infrastructure Layer                         |
|  Adapters: NixAdapter, TmuxAdapter, FabricAdapter              |
|  Repositories: SQLiteRepository, PlaybookRepository            |
|  Event Bus (in-memory)  |  Agent Registry  |  Config Loader   |
|  Telemetry (OpenTelemetry)  |  Node Agent                     |
+---------------------------------------------------------------+
```

## Key Design Patterns

### Ports and Adapters (Hexagonal Architecture)

The domain layer defines **port protocols** that describe what capabilities it needs without specifying how they are implemented. Infrastructure adapters implement these ports.

| Port                  | Purpose                              | Adapter(s)           |
|-----------------------|--------------------------------------|----------------------|
| `NixPort`             | Nix build, instantiate, shell        | `NixAdapter`         |
| `SessionPort`         | Persistent session management        | `TmuxAdapter`        |
| `RemoteExecutorPort`  | Remote command execution             | `FabricAdapter`      |
| `CloudProviderPort`   | Multi-cloud node discovery           | AWS/GCP/Azure        |
| `EventBusPort`        | Domain event pub/sub                 | `EventBus` (memory)  |
| `OrchestratorPort`    | Agent-to-orchestrator communication  | MCP/gRPC/HTTP        |
| `ITSMPort`            | Incident management (ServiceNow, Jira) | ITSM adapters     |
| `NotificationPort`    | Alerts via Slack, PagerDuty, email   | Notification adapters|

All ports use Python `Protocol` with `@runtime_checkable` for structural typing -- adapters do not need to inherit from the port, they just need to implement the same method signatures.

### Dependency Injection via Composition Root

All dependency wiring happens in a single module: `chimera/composition_root.py`. A `ChimeraContainer` dataclass holds all adapters and use cases. The factory function `create_container()` instantiates and connects everything:

```python
def create_container() -> ChimeraContainer:
    nix_adapter = NixAdapter()
    tmux_adapter = TmuxAdapter()
    fabric_adapter = FabricAdapter()
    event_bus = EventBus()

    deploy_fleet = DeployFleet(nix_adapter, fabric_adapter)
    execute_local = ExecuteLocalDeployment(nix_adapter, tmux_adapter)
    rollback = RollbackDeployment(fabric_adapter)
    autonomous_loop = AutonomousLoop(nix_adapter, fabric_adapter, deploy_fleet)

    return ChimeraContainer(...)
```

No adapter is instantiated outside this module. No DI framework is used -- just a simple dataclass container and a factory function.

### Frozen Dataclasses and Immutability

Domain entities and value objects use `@dataclass(frozen=True)` to enforce immutability. State transitions on the `Deployment` aggregate return new instances rather than mutating in place:

```python
@dataclass(frozen=True)
class Deployment:
    status: DeploymentStatus = DeploymentStatus.PENDING

    def start_build(self) -> Deployment:
        # Returns a NEW Deployment with BUILDING status
        return Deployment(..., status=DeploymentStatus.BUILDING, ...)
```

This ensures auditability and thread safety -- no shared mutable state.

### Domain Events

Entities accumulate domain events as immutable tuples. Events are published through the `EventBusPort` after a use case completes. The in-memory `EventBus` dispatches events to async subscriber handlers:

- `DeploymentStartedEvent` -- published when a deployment begins
- `DeploymentBuildCompletedEvent` -- published when Nix build finishes
- `DeploymentCompletedEvent` -- published when deployment succeeds
- `DeploymentFailedEvent` -- published when deployment fails

### Policy Engine (RBAC)

The `PolicyEngine` evaluates authorization using role-based access control. Predefined roles (`viewer`, `operator`, `admin`) group granular permissions (`DEPLOY`, `ROLLBACK`, `HEAL_RESTART`, `HEAL_REBUILD`, etc.). Evaluation follows explicit deny > allow > default deny semantics.

## Module Structure

```
chimera/
  composition_root.py              # DI wiring
  domain/
    entities/
      deployment.py                # Deployment aggregate root
      nix_config.py                # NixConfig entity
      slo.py                       # SLO/SLA entity with error budgets
      playbook.py                  # Remediation playbook aggregate
      policy.py                    # RBAC policy engine
    events/
      event_base.py                # DomainEvent base class
    ports/
      nix_port.py                  # Nix ecosystem port
      session_port.py              # Session management port
      remote_executor_port.py      # Remote execution port
      cloud_provider_port.py       # Multi-cloud provider port
      event_bus_port.py            # Event publishing port
      orchestrator_port.py         # Agent-orchestrator port
      itsm_port.py                 # Incident management port
      notification_port.py         # Alert/notification port
    services/
      drift_detection.py           # Drift analysis and healing plans
      predictive_analytics.py      # Risk scoring and trend detection
      root_cause_analysis.py       # Causal AI for drift root causes
      playbook_engine.py           # Playbook execution engine
    value_objects/
      nix_hash.py                  # NixHash value object
      node.py                      # Node value object
      session_id.py                # SessionId value object
      congruence_report.py         # Congruence check result
  application/
    use_cases/
      deploy_fleet.py              # Deploy to multiple nodes
      execute_local_deployment.py  # Deploy locally via Tmux
      rollback_deployment.py       # Rollback to previous generation
      autonomous_loop.py           # Continuous drift watch + heal
    orchestration/
      dag_orchestrator.py          # DAG-based deployment orchestration
  infrastructure/
    adapters/
      nix_adapter.py               # Nix CLI adapter
      tmux_adapter.py              # Tmux session adapter
      fabric_adapter.py            # Fabric/SSH remote executor
    repositories/
      sqlite_repository.py         # SQLite persistence
      playbook_repository.py       # Playbook storage
    mcp_servers/
      chimera_server.py            # MCP server for AI agents
    agent/
      chimera_agent.py             # Node agent daemon
      agent_registry.py            # Fleet agent registry
    config.py                      # Configuration loader
    event_bus.py                   # In-memory event bus
    logging.py                     # Logging configuration
    telemetry/                     # OpenTelemetry integration
  presentation/
    cli/
      cli.py                       # CLI entry point (argparse)
    tui/
      dashboard.py                 # Textual-based TUI dashboard
    web/
      app.py                       # Web dashboard
```

## MCP Integration Pattern

Chimera exposes its deployment domain capabilities via the Model Context Protocol (MCP), enabling AI agents to interact with fleet operations programmatically.

### Architecture

Each bounded context has exactly one MCP server. The `chimera-service` server is created by a factory function that receives wired use cases from the composition root:

```python
server = create_chimera_server(container.deploy_fleet, container.rollback)
```

### Tools vs Resources

MCP follows a strict separation:

- **Tools** = write operations (commands that change state)
  - `execute_deployment` -- deploy to targets
  - `rollback_deployment` -- rollback to previous generation
  - `check_congruence` -- verify fleet configuration consistency
- **Resources** = read operations (queries that return data)
  - `node://health` -- get health status of all nodes
  - `deployment://{session_id}` -- get deployment status

### Error Handling

MCP errors use structured `MCPError` with error codes:
- `tool_not_found` -- requested tool does not exist
- `resource_not_found` -- requested resource does not exist
- `internal_error` -- unexpected failure during execution

Tools return status dictionaries with `status`, `message`, and contextual fields rather than raising exceptions to the MCP caller.
