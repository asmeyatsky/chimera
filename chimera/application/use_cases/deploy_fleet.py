"""
Deploy Fleet Use Case

Architectural Intent:
- Orchestrates fleet deployment across multiple nodes
- Builds Nix derivation, syncs closure, creates sessions, and executes commands
- Uses parallel execution where possible
"""

from typing import List
from pathlib import Path
from chimera.domain.entities.deployment import Deployment, DeploymentStatus
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.node import Node
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.ports.session_port import SessionPort
from chimera.domain.ports.remote_executor_port import RemoteExecutorPort


class DeployFleet:
    def __init__(
        self,
        nix_port: NixPort,
        remote_executor: RemoteExecutorPort,
        session_port: SessionPort | None = None,
    ):
        self.nix_port = nix_port
        self.remote_executor = remote_executor

    async def execute(
        self, config_path: str, command: str, session_name: str, targets: List[str]
    ) -> bool:
        config = NixConfig(Path(config_path))
        nodes = [Node.parse(t) for t in targets]

        try:
            nix_hash = await self.nix_port.build(str(config.path))
        except Exception as e:
            print(f"Build failed: {e}")
            return False

        if not await self.remote_executor.sync_closure(nodes, str(nix_hash)):
            print("Sync failed")
            return False

        tmux_cmd = "/usr/local/bin/tmux"
        session_cmd = f"{tmux_cmd} new-session -d -s {session_name} || true"
        if not await self.remote_executor.exec_command(nodes, session_cmd):
            print("Session creation failed")
            return False

        cmd_to_send = await self.nix_port.shell(str(config.path), command)
        tmux_send = f"{tmux_cmd} send-keys -t {session_name} '{cmd_to_send}' C-m"

        if not await self.remote_executor.exec_command(nodes, tmux_send):
            print("Command execution failed")
            return False

        print(f"Deployment successful to {len(nodes)} nodes.")
        return True
