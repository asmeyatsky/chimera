"""
Chimera Agent Module

Architectural Intent:
- Node agent that runs on each infrastructure node
- Reports health, detects drift, executes healing
- Communicates with central orchestrator via MCP/gRPC
- Exports metrics via OpenTelemetry

Agent Responsibilities:
1. Health monitoring (heartbeat)
2. Configuration drift detection
3. Healing execution (rollback/remediate)
4. Metrics export (OTLP)

Security:
- Healing commands validated against allowlist (no arbitrary shell execution)
- Healing command files stored in /var/lib/chimera/healing/ (not /tmp/)
- File ownership and permission checks before executing healing commands
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto
from typing import Optional, Any
import asyncio
import hashlib
import logging
import os
import shlex
import stat
import subprocess

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = frozenset({
    "nix-env",
    "nixos-rebuild",
    "systemctl",
    "nix-build",
    "nix-store",
})

HEALING_DIR = "/var/lib/chimera/healing"


class AgentStatus(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    DRIFT_DETECTED = auto()
    HEALING = auto()
    UNREACHABLE = auto()
    UNKNOWN = auto()


class DriftSeverity(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass(frozen=True)
class NodeHealth:
    node_id: str
    status: AgentStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    nix_version: Optional[str] = None
    current_hash: Optional[str] = None
    expected_hash: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        return self.status == AgentStatus.HEALTHY

    @property
    def has_drift(self) -> bool:
        if self.current_hash and self.expected_hash:
            return self.current_hash != self.expected_hash
        return False


@dataclass(frozen=True)
class DriftReport:
    node_id: str
    expected_hash: str
    actual_hash: str
    severity: DriftSeverity
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: str = ""

    @property
    def is_drift(self) -> bool:
        return self.expected_hash != self.actual_hash


@dataclass
class AgentConfig:
    node_id: str
    heartbeat_interval: int = 5
    drift_check_interval: int = 30
    auto_heal: bool = True
    rollback_on_drift: bool = True
    orchestrator_url: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    log_level: str = "INFO"


def _validate_healing_command(command: str) -> list[str]:
    """Parse and validate a healing command against the allowlist.

    Returns the parsed command as a list of arguments.
    Raises ValueError if the command is not allowed.
    """
    parts = shlex.split(command)
    if not parts:
        raise ValueError("Empty healing command")

    executable = os.path.basename(parts[0])
    if executable not in ALLOWED_COMMANDS:
        raise ValueError(
            f"Command '{executable}' not in allowlist. "
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )
    return parts


def _validate_healing_file(path: str) -> None:
    """Validate that a healing command file is safe to read.

    Checks:
    - File is owned by root (uid 0)
    - File is not world-writable
    """
    try:
        st = os.stat(path)
    except OSError:
        raise ValueError(f"Cannot stat healing file: {path}")

    if st.st_uid != 0:
        raise ValueError(
            f"Healing file {path} not owned by root (owner uid={st.st_uid})"
        )

    if st.st_mode & stat.S_IWOTH:
        raise ValueError(f"Healing file {path} is world-writable")


class ChimeraAgent:
    """
    Agent running on each node in the fleet.

    Responsibilities:
    - Emit heartbeats to orchestrator
    - Check configuration drift
    - Execute healing commands when authorized
    - Export metrics via OTLP
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._running = False
        self._health = NodeHealth(
            node_id=config.node_id,
            status=AgentStatus.UNKNOWN,
        )
        self._last_drift_report: Optional[DriftReport] = None

    @property
    def node_id(self) -> str:
        return self.config.node_id

    @property
    def health(self) -> NodeHealth:
        return self._health

    async def start(self) -> None:
        """Start the agent's monitoring loops."""
        self._running = True
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._drift_check_loop())
        asyncio.create_task(self._healing_loop())

    async def stop(self) -> None:
        """Stop the agent."""
        self._running = False

    async def _heartbeat_loop(self) -> None:
        """Emit periodic heartbeats to orchestrator."""
        while self._running:
            try:
                await self._emit_heartbeat()
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)
                self._health = NodeHealth(
                    node_id=self.config.node_id,
                    status=AgentStatus.UNREACHABLE,
                )
            await asyncio.sleep(self.config.heartbeat_interval)

    async def _drift_check_loop(self) -> None:
        """Check for configuration drift periodically."""
        while self._running:
            try:
                await self._check_drift()
            except Exception as e:
                logger.warning("Drift check failed: %s", e)
            await asyncio.sleep(self.config.drift_check_interval)

    async def _healing_loop(self) -> None:
        """Process healing commands from orchestrator."""
        while self._running:
            try:
                await self._check_healing_commands()
            except Exception as e:
                logger.warning("Healing loop error: %s", e)
            await asyncio.sleep(1)

    async def _emit_heartbeat(self) -> None:
        """Emit heartbeat to orchestrator."""
        self._health = NodeHealth(
            node_id=self.config.node_id,
            status=AgentStatus.HEALTHY,
            nix_version=await self._get_nix_version(),
            current_hash=await self._get_current_hash(),
            expected_hash=await self._get_expected_hash(),
        )

    async def _check_drift(self) -> None:
        """Check if configuration has drifted from expected state."""
        current = await self._get_current_hash()
        expected = await self._get_expected_hash()

        if current and expected and current != expected:
            severity = self._calculate_drift_severity(current, expected)
            self._last_drift_report = DriftReport(
                node_id=self.config.node_id,
                expected_hash=expected,
                actual_hash=current,
                severity=severity,
                details=f"Drift detected: expected={expected}, actual={current}",
            )
            self._health = NodeHealth(
                node_id=self.config.node_id,
                status=AgentStatus.DRIFT_DETECTED,
                current_hash=current,
                expected_hash=expected,
            )

    def _calculate_drift_severity(self, current: str, expected: str) -> DriftSeverity:
        """Calculate severity based on drift characteristics."""
        if current == "00000000000000000000000000000000":
            return DriftSeverity.CRITICAL
        return DriftSeverity.HIGH

    async def _get_nix_version(self) -> Optional[str]:
        """Get installed Nix version."""
        try:
            result = subprocess.run(
                ["nix", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    async def _get_current_hash(self) -> Optional[str]:
        """Get current system configuration hash."""
        try:
            result = subprocess.run(
                [
                    "nix-env",
                    "--query",
                    "--profile",
                    "/nix/var/nix/profiles/system",
                    "--out-path",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    hash_part = path.split("-")[-1] if "-" in path else path
                    return hash_part[:32]
        except Exception:
            pass
        return None

    async def _get_expected_hash(self) -> Optional[str]:
        """Get expected hash from orchestrator or local cache."""
        cache_path = os.path.join(HEALING_DIR, "expected_hash")
        try:
            with open(cache_path, "r") as f:
                return f.read().strip()
        except Exception:
            return None

    async def _check_healing_commands(self) -> None:
        """Check for and process healing commands.

        Security: Reads from /var/lib/chimera/healing/, validates file ownership,
        atomically deletes before executing to prevent re-execution.
        """
        cmd_path = os.path.join(HEALING_DIR, f"heal_{self.config.node_id}")
        try:
            _validate_healing_file(cmd_path)

            with open(cmd_path, "r") as f:
                cmd = f.read().strip()

            # Atomically delete before executing to prevent re-execution
            os.remove(cmd_path)

            if cmd:
                self._health = NodeHealth(
                    node_id=self.config.node_id,
                    status=AgentStatus.HEALING,
                )
                await self._execute_healing(cmd)
        except FileNotFoundError:
            pass
        except ValueError as e:
            logger.error("Healing file validation failed: %s", e)
        except Exception as e:
            logger.error("Unexpected error in healing check: %s", e)

    async def _execute_healing(self, command: str) -> None:
        """Execute healing command after validation against allowlist."""
        try:
            cmd_parts = _validate_healing_command(command)

            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info("Healing command succeeded: %s", cmd_parts[0])
                self._health = NodeHealth(
                    node_id=self.config.node_id,
                    status=AgentStatus.HEALTHY,
                )
            else:
                logger.warning(
                    "Healing command failed (exit %d): %s",
                    result.returncode,
                    result.stderr,
                )
                self._health = NodeHealth(
                    node_id=self.config.node_id,
                    status=AgentStatus.DEGRADED,
                )
        except ValueError as e:
            logger.error("Healing command rejected: %s", e)
            self._health = NodeHealth(
                node_id=self.config.node_id,
                status=AgentStatus.DEGRADED,
            )
        except Exception as e:
            logger.error("Healing execution failed: %s", e)
            self._health = NodeHealth(
                node_id=self.config.node_id,
                status=AgentStatus.DEGRADED,
            )

    def get_drift_report(self) -> Optional[DriftReport]:
        """Get the latest drift report."""
        return self._last_drift_report

    def to_dict(self) -> dict[str, Any]:
        """Serialize agent state for export."""
        return {
            "node_id": self.config.node_id,
            "status": self._health.status.name,
            "timestamp": self._health.timestamp.isoformat(),
            "has_drift": self._health.has_drift,
            "current_hash": self._health.current_hash,
            "expected_hash": self._health.expected_hash,
            "drift_report": {
                "severity": self._last_drift_report.severity.name,
                "detected_at": self._last_drift_report.detected_at.isoformat(),
                "details": self._last_drift_report.details,
            }
            if self._last_drift_report
            else None,
        }
