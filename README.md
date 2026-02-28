# Chimera: Autonomous Determinism Engine

> Deploy to 1000+ nodes, let it heal itself forever. Never SSH into production again.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://github.com/asmeyatsky/chimera)
[![Tests](https://img.shields.io/badge/tests-541%20passing-brightgreen.svg)](https://github.com/asmeyatsky/chimera)
[![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen.svg)](https://github.com/asmeyatsky/chimera)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/asmeyatsky/chimera/blob/main/LICENSE)

## What is Chimera?

Chimera is an autonomous deployment engine that combines Nix reproducibility with self-healing capabilities. It guarantees every node in a fleet converges to the same configuration state, detects when they drift, and heals them automatically.

```bash
# Deploy to fleet
chimera deploy -t "user@server1,user@server2,user@server3" -c production.nix "nixos-rebuild switch"

# Start autonomous monitoring — infrastructure heals itself while you sleep
chimera watch -t "user@server1,user@server2,user@server3"
```

## Features

**Deterministic Deployments** — Nix closures synced to remote nodes via SSH, executed in persistent Tmux sessions. DAG orchestrator ensures correct build/sync/execute ordering.

**Autonomous Drift Detection** — Continuous monitoring compares expected vs actual Nix store hashes. Severity classification (LOW/MEDIUM/HIGH/CRITICAL) with blast radius calculation across the fleet.

**Self-Healing** — Automatic remediation based on severity: restart services, rebuild configurations, or rollback to previous NixOS generations. Policy engine with RBAC controls healing authorization.

**Time Machine Rollback** — Instant rollback to any previous NixOS generation across the entire fleet.

**Fleet Orchestration** — Deploy, rollback, and monitor multiple nodes in parallel. Agent registry tracks per-node health and drift status.

**Predictive Analytics** — Risk scoring per node using drift frequency, severity trends, and MTTR tracking. Trend detection flags nodes before they fail.

**Root Cause Analysis** — Causal AI correlating temporal, spatial, and deployment signals to identify why drift occurred.

**Remediation Playbooks** — Validated, marketplace-style playbooks with step-by-step healing procedures and rollback on failure.

**MCP Integration** — Model Context Protocol server exposing deployment capabilities to AI agents via stdio JSON-RPC transport.

**Multi-Cloud Support** — AWS, GCP, and Azure adapters for node discovery, provisioning, and auto-scaling integration.

**Notifications** — Slack webhooks, PagerDuty, and email alerts for drift events and healing actions.

**SLO/SLA Tracking** — Error budget monitoring with violation detection and window-based availability calculations.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Nix package manager
- tmux

### Install

```bash
pip install .

# With optional dependencies
pip install ".[ssh]"    # SSH/remote execution (Fabric)
pip install ".[tui]"    # TUI dashboard (Textual)
pip install ".[all]"    # Everything
pip install ".[dev]"    # Development (pytest, ruff)
```

### Basic Usage

```bash
# Run locally in a Nix+Tmux environment
chimera run -c default.nix "echo hello"

# Deploy to fleet
chimera deploy -t "root@10.0.0.1:22,root@10.0.0.2:22" -c production.nix "nixos-rebuild switch"

# Rollback fleet to previous generation
chimera rollback -t "root@10.0.0.1:22,root@10.0.0.2:22"

# Autonomous drift watch with self-healing
chimera watch -t "root@10.0.0.1:22,root@10.0.0.2:22" --interval 30

# Web dashboard
chimera web --port 8080

# Node agent daemon
chimera agent --node-id node-01

# MCP server for AI agents
chimera mcp
```

### Configuration

Create `chimera.json` in your working directory:

```json
{
  "log_level": "INFO",
  "fleet": {
    "targets": ["root@10.0.0.1:22", "root@10.0.0.2:22"]
  },
  "watch": {
    "interval_seconds": 30
  },
  "web": {
    "host": "127.0.0.1",
    "port": 8080
  },
  "notifications": {
    "slack_webhook_url": "https://hooks.slack.com/services/..."
  }
}
```

Environment variables override file config with the pattern `CHIMERA_SECTION_KEY`:

```bash
export CHIMERA_WEB_PORT=9090
export CHIMERA_FLEET_TARGETS="node1,node2,node3"
```

---

## Architecture

Chimera follows hexagonal architecture (ports and adapters) with domain-driven design:

```
Presentation    CLI · TUI Dashboard · Web Dashboard · MCP Server
Application     DeployFleet · ExecuteLocal · Rollback · AutonomousLoop
Domain          Deployment · SLO · Playbook · Policy · DriftDetection · RCA
Infrastructure  Nix · Tmux · Fabric/SSH · SQLite · EventBus · OTEL
```

- **8 Protocol-based ports** — Nix, Session, RemoteExecutor, CloudProvider, EventBus, Orchestrator, ITSM, Notification
- **Composition root** — Single `create_container()` factory wires all dependencies
- **Frozen dataclasses** — Immutable entities, state transitions return new instances
- **Domain events** — Event bus publishes deployment lifecycle events
- **Zero runtime dependencies** — Core uses only Python stdlib (sqlite3, asyncio, json, subprocess)

---

## Documentation

- [Getting Started](docs/getting-started.md) — Installation, configuration, basic usage
- [Architecture Guide](docs/architecture.md) — Design patterns, layer diagram, module structure
- [API Reference](docs/api-reference.md) — CLI commands, MCP tools, config options, domain ports
- [Cloud Providers](docs/cloud-providers.md) — AWS, GCP, Azure setup and node discovery

---

## Development

```bash
# Install dev dependencies
pip install ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=chimera

# Lint
ruff check chimera/
```

541 tests, 86% coverage, CI via GitHub Actions.

---

## License

MIT License. See [LICENSE](LICENSE).
