"""
Deploy Fleet Use Case

Architectural Intent:
- Orchestrates fleet deployment across multiple nodes
- Builds Nix derivation, syncs closure, creates sessions, and executes commands
- Uses DAGOrchestrator for dependency-ordered parallel execution

Security:
- All tmux arguments quoted via shlex.quote() to prevent shell injection
- Uses PATH resolution for tmux (not hardcoded path)
"""

import shlex
import logging
from typing import List, Any
from pathlib import Path
from chimera.domain.entities.deployment import Deployment, DeploymentStatus
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.node import Node
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.ports.remote_executor_port import RemoteExecutorPort
from chimera.application.orchestration.dag_orchestrator import (
    DAGOrchestrator,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class DeployFleet:
    def __init__(
        self,
        nix_port: NixPort,
        remote_executor: RemoteExecutorPort,
    ):
        self.nix_port = nix_port
        self.remote_executor = remote_executor

    async def execute(
        self, config_path: str, command: str, session_name: str, targets: List[str]
    ) -> bool:
        config = NixConfig(Path(config_path))
        nodes = [Node.parse(t) for t in targets]

        async def build_step(context: dict[str, Any], results: dict[str, Any]) -> str:
            nix_hash = await self.nix_port.build(str(config.path))
            return str(nix_hash)

        async def sync_step(context: dict[str, Any], results: dict[str, Any]) -> bool:
            nix_hash = results["build"]
            if not await self.remote_executor.sync_closure(nodes, nix_hash):
                raise RuntimeError("Sync failed")
            return True

        async def session_step(context: dict[str, Any], results: dict[str, Any]) -> bool:
            safe_session = shlex.quote(session_name)
            session_cmd = f"tmux new-session -d -s {safe_session} || true"
            if not await self.remote_executor.exec_command(nodes, session_cmd):
                raise RuntimeError("Session creation failed")
            return True

        async def execute_step(context: dict[str, Any], results: dict[str, Any]) -> bool:
            cmd_to_send = await self.nix_port.shell(str(config.path), command)
            safe_session = shlex.quote(session_name)
            safe_cmd = shlex.quote(cmd_to_send)
            tmux_send = f"tmux send-keys -t {safe_session} {safe_cmd} C-m"
            if not await self.remote_executor.exec_command(nodes, tmux_send):
                raise RuntimeError("Command execution failed")
            return True

        orchestrator = DAGOrchestrator([
            WorkflowStep("build", build_step, depends_on=[]),
            WorkflowStep("sync", sync_step, depends_on=["build"]),
            WorkflowStep("session", session_step, depends_on=["build"]),
            WorkflowStep("execute", execute_step, depends_on=["sync", "session"]),
        ])

        try:
            await orchestrator.execute({})
            logger.info("Deployment successful to %d nodes.", len(nodes))
            return True
        except Exception as e:
            logger.error("Deployment failed: %s", e)
            return False
