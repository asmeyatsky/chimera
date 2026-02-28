"""
Configuration Module

Architectural Intent:
- Centralized configuration loading from YAML files
- Provides typed access to all Chimera settings
- Falls back to sensible defaults when config file is absent
- Environment variables override file-based config

Design Decisions:
- Uses stdlib tomllib (Python 3.11+) for TOML, or fallback YAML-like parser
- Config is a frozen dataclass for immutability after load
- Nested config sections map to sub-dataclasses
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NixConfig:
    """Nix build configuration."""
    config_path: str = "default.nix"


@dataclass(frozen=True)
class FleetConfig:
    """Fleet target configuration."""
    targets: tuple[str, ...] = ()
    session_name: str = "chimera-deploy"


@dataclass(frozen=True)
class WatchConfig:
    """Autonomous watch configuration."""
    interval_seconds: int = 10
    session_name: str = "chimera-watch"


@dataclass(frozen=True)
class AgentNodeConfig:
    """Node agent configuration."""
    node_id: str = ""
    heartbeat_interval: int = 5
    drift_check_interval: int = 30
    auto_heal: bool = True


@dataclass(frozen=True)
class WebConfig:
    """Web dashboard configuration."""
    host: str = "127.0.0.1"
    port: int = 8080


@dataclass(frozen=True)
class MCPConfig:
    """MCP server configuration."""
    host: str = "localhost"
    port: int = 8765


@dataclass(frozen=True)
class TelemetryConfig:
    """OpenTelemetry configuration."""
    endpoint: str = ""
    insecure: bool = False


@dataclass(frozen=True)
class ITSMConfig:
    """ITSM integration configuration."""
    provider: str = ""  # "servicenow" or "jira"
    url: str = ""
    username: str = ""
    api_key: str = ""
    project_key: str = ""


@dataclass(frozen=True)
class NotificationsConfig:
    """Notification configuration."""
    slack_webhook_url: str = ""
    pagerduty_api_key: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_from: str = ""
    email_to: str = ""


@dataclass(frozen=True)
class ChimeraConfig:
    """Root configuration for the Chimera application."""
    nix: NixConfig = field(default_factory=NixConfig)
    fleet: FleetConfig = field(default_factory=FleetConfig)
    watch: WatchConfig = field(default_factory=WatchConfig)
    agent: AgentNodeConfig = field(default_factory=AgentNodeConfig)
    web: WebConfig = field(default_factory=WebConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    itsm: ITSMConfig = field(default_factory=ITSMConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    log_level: str = "WARNING"


def _env_override(data: dict, prefix: str = "CHIMERA") -> dict:
    """Override config values with environment variables.

    Environment variables follow the pattern CHIMERA_SECTION_KEY.
    For example: CHIMERA_WEB_PORT=9090, CHIMERA_FLEET_TARGETS=10.0.0.1,10.0.0.2
    """
    for key, value in os.environ.items():
        if not key.startswith(f"{prefix}_"):
            continue
        parts = key[len(prefix) + 1:].lower().split("_", 1)
        if len(parts) == 2:
            section, field_name = parts
            if section not in data:
                data[section] = {}
            data[section][field_name] = value
        elif len(parts) == 1:
            data[parts[0]] = value
    return data


def _parse_config_file(path: Path) -> dict:
    """Parse a JSON config file. Returns empty dict on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.debug("Config file not found: %s", path)
        return {}
    except json.JSONDecodeError as e:
        logger.warning("Invalid config file %s: %s", path, e)
        return {}


def _build_sub_config(cls, data: dict):
    """Build a sub-config dataclass from a dict, ignoring unknown keys."""
    import dataclasses
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_fields}

    # Convert comma-separated strings to tuples for tuple fields
    for f in dataclasses.fields(cls):
        if f.name in filtered and f.type == "tuple[str, ...]":
            val = filtered[f.name]
            if isinstance(val, str):
                filtered[f.name] = tuple(v.strip() for v in val.split(",") if v.strip())
            elif isinstance(val, list):
                filtered[f.name] = tuple(val)

        # Convert string numbers to int/bool
        if f.name in filtered and isinstance(filtered[f.name], str):
            if f.type == "int":
                filtered[f.name] = int(filtered[f.name])
            elif f.type == "bool":
                filtered[f.name] = filtered[f.name].lower() in ("true", "1", "yes")

    return cls(**filtered)


def load_config(
    path: Optional[str] = None,
    env_prefix: str = "CHIMERA",
) -> ChimeraConfig:
    """Load configuration from file and environment variables.

    Priority (highest to lowest):
    1. Environment variables (CHIMERA_SECTION_KEY)
    2. Config file values
    3. Defaults

    Args:
        path: Path to config file (JSON). Defaults to chimera.json in CWD.
        env_prefix: Environment variable prefix. Defaults to CHIMERA.
    """
    config_path = Path(path) if path else Path("chimera.json")
    data = _parse_config_file(config_path)
    data = _env_override(data, env_prefix)

    return ChimeraConfig(
        nix=_build_sub_config(NixConfig, data.get("nix", {})),
        fleet=_build_sub_config(FleetConfig, data.get("fleet", {})),
        watch=_build_sub_config(WatchConfig, data.get("watch", {})),
        agent=_build_sub_config(AgentNodeConfig, data.get("agent", {})),
        web=_build_sub_config(WebConfig, data.get("web", {})),
        mcp=_build_sub_config(MCPConfig, data.get("mcp", {})),
        telemetry=_build_sub_config(TelemetryConfig, data.get("telemetry", {})),
        itsm=_build_sub_config(ITSMConfig, data.get("itsm", {})),
        notifications=_build_sub_config(
            NotificationsConfig, data.get("notifications", {})
        ),
        log_level=data.get("log_level", "WARNING"),
    )
