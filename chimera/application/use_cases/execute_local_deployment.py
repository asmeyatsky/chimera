"""
Execute Local Deployment Use Case

Architectural Intent:
- Orchestrates local deployment process using DAG workflow
- Coordinates Nix build, session creation, and command execution
- Parallelizes independent steps where possible
"""

from pathlib import Path
from chimera.domain.entities.deployment import Deployment, DeploymentStatus
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.ports.session_port import SessionPort
from chimera.application.orchestration.dag_orchestrator import (
    DAGOrchestrator,
    WorkflowStep,
)


class ExecuteLocalDeployment:
    def __init__(self, nix_port: NixPort, session_port: SessionPort):
        self.nix_port = nix_port
        self.session_port = session_port

    async def execute(
        self, config_path: str, command: str, session_name: str
    ) -> SessionId:
        config = NixConfig(Path(config_path))
        session_id = SessionId(session_name)

        deployment = Deployment(session_id=session_id, config=config)
        deployment = deployment.start_build()

        try:
            nix_hash = await self.nix_port.build(str(config.path))
            deployment = deployment.complete_build(nix_hash)

            await self.session_port.create_session(session_id)

            shell_cmd = await self.nix_port.shell(str(config.path), command)

            success = await self.session_port.run_command(session_id, shell_cmd)
            if not success:
                raise RuntimeError("Failed to send command to Tmux session")

            deployment = deployment.complete()
            return session_id

        except Exception as e:
            deployment = deployment.fail(str(e))
            raise e
