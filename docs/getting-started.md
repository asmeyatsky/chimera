# Getting Started with Chimera

## Prerequisites

- **Python 3.11+** (Python 3.12 also supported)
- **Nix** package manager (for deterministic builds and deployments)
- **tmux** (for persistent session management)
- **SSH access** to target nodes (for fleet deployments)

## Installation

### Basic installation

```bash
pip install .
```

### With optional dependencies

```bash
# SSH/remote execution support (Fabric)
pip install ".[ssh]"

# TUI dashboard (Textual)
pip install ".[tui]"

# All optional dependencies
pip install ".[all]"

# Development dependencies (pytest, ruff, etc.)
pip install ".[dev]"
```

After installation, the `chimera` command is available on your PATH.

## Configuration

Chimera loads configuration from a JSON file and environment variables. The priority order is:

1. **Environment variables** (highest priority)
2. **Config file values**
3. **Built-in defaults** (lowest priority)

### Config file

By default, Chimera looks for `chimera.json` in the current working directory. Example:

```json
{
  "log_level": "INFO",
  "nix": {
    "config_path": "default.nix"
  },
  "fleet": {
    "targets": ["root@10.0.0.1:22", "root@10.0.0.2:22"],
    "session_name": "chimera-deploy"
  },
  "watch": {
    "interval_seconds": 10,
    "session_name": "chimera-watch"
  },
  "agent": {
    "node_id": "node-01",
    "heartbeat_interval": 5,
    "drift_check_interval": 30,
    "auto_heal": true
  },
  "web": {
    "host": "127.0.0.1",
    "port": 8080
  },
  "mcp": {
    "host": "localhost",
    "port": 8765
  },
  "telemetry": {
    "endpoint": "http://localhost:4317",
    "insecure": false
  },
  "itsm": {
    "provider": "servicenow",
    "url": "https://instance.service-now.com",
    "username": "chimera-bot",
    "api_key": "",
    "project_key": ""
  },
  "notifications": {
    "slack_webhook_url": "https://hooks.slack.com/services/...",
    "pagerduty_api_key": "",
    "email_smtp_host": "",
    "email_smtp_port": 587,
    "email_from": "",
    "email_to": ""
  }
}
```

### Environment variables

Environment variables follow the pattern `CHIMERA_SECTION_KEY` and override config file values. Examples:

```bash
export CHIMERA_FLEET_TARGETS="root@10.0.0.1:22,root@10.0.0.2:22"
export CHIMERA_WEB_PORT=9090
export CHIMERA_WATCH_INTERVAL_SECONDS=30
export CHIMERA_LOG_LEVEL=DEBUG
```

## Basic Usage

### Run a command locally

Execute a command in a persistent Nix+Tmux environment:

```bash
chimera run "echo hello world"
chimera run --config my-env.nix --session my-session "python app.py"
```

Options:
- `--config, -c` -- Path to Nix config file (default: `default.nix`)
- `--session, -s` -- Tmux session name (default: `chimera-default`)

### Attach to a session

Reconnect to a running Chimera session:

```bash
chimera attach chimera-default
```

### Deploy to a fleet

Deploy a command across multiple remote nodes:

```bash
chimera deploy --targets root@10.0.0.1:22,root@10.0.0.2:22 "nixos-rebuild switch"
chimera deploy -t node1,node2,node3 -c production.nix "systemctl restart myapp"
```

Options:
- `--targets, -t` (required) -- Comma-separated list of target nodes
- `--config, -c` -- Path to Nix config file (default: `default.nix`)
- `--session, -s` -- Remote session name (default: `chimera-deploy`)

### Rollback a deployment

Roll back nodes to a previous NixOS generation:

```bash
chimera rollback --targets root@10.0.0.1:22,root@10.0.0.2:22
chimera rollback -t node1,node2 --generation 42
```

Options:
- `--targets, -t` (required) -- Comma-separated list of target nodes
- `--generation, -g` -- Specific generation number to roll back to (optional; defaults to previous)

### Autonomous drift watch

Start continuous drift detection and self-healing:

```bash
chimera watch --targets root@10.0.0.1:22,root@10.0.0.2:22
chimera watch -t node1,node2 --interval 30 --config production.nix
chimera watch -t node1 --once  # Run a single check and exit
```

Options:
- `--targets, -t` (required) -- Comma-separated list of target nodes
- `--config, -c` -- Path to Nix config file (default: `default.nix`)
- `--interval, -i` -- Check interval in seconds (default: `10`)
- `--session, -s` -- Session name for healing (default: `chimera-watch`)
- `--once` -- Run once and exit

### Fleet dashboard (TUI)

Launch an interactive terminal dashboard for fleet monitoring:

```bash
chimera dash --targets root@10.0.0.1:22,root@10.0.0.2:22
```

Requires the `tui` optional dependency (`pip install ".[tui]"`).

### Web dashboard

Start a web-based dashboard:

```bash
chimera web
chimera web --port 9090 --host 0.0.0.0
```

Options:
- `--port, -p` -- Web server port (default: `8080`)
- `--host` -- Web server bind address (default: `127.0.0.1`)

## Running the MCP Server

Start the MCP server to expose Chimera's deployment capabilities to AI agents:

```bash
chimera mcp
chimera mcp --port 9000 --host 0.0.0.0
```

Options:
- `--port, -p` -- MCP server port (default: `8765`)
- `--host` -- MCP server bind address (default: `localhost`)

The server registers tools (`execute_deployment`, `rollback_deployment`, `check_congruence`) and resources (`node://health`, `deployment://{session_id}`) for programmatic interaction.

## Running the Node Agent

Start the Chimera agent daemon on a managed node:

```bash
chimera agent --node-id node-01
chimera agent --node-id node-01 --heartbeat 10 --drift-interval 60
chimera agent --node-id node-01 --no-auto-heal
```

Options:
- `--node-id` (required) -- Unique identifier for this node
- `--heartbeat` -- Heartbeat interval in seconds (default: `5`)
- `--drift-interval` -- Drift check interval in seconds (default: `30`)
- `--no-auto-heal` -- Disable automatic healing

## Running Tests

```bash
# Install dev dependencies
pip install ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=chimera

# Run a specific test file
pytest tests/test_deployment.py
```

## Logging and Debug Output

Use `--verbose` or `--debug` flags on any command for more output:

```bash
chimera --verbose deploy -t node1 "nixos-rebuild switch"
chimera --debug watch -t node1,node2
```

- `--verbose, -v` -- Sets log level to INFO
- `--debug` -- Sets log level to DEBUG and shows full tracebacks on error
