from pathlib import Path
from chimera.domain.entities.deployment import Deployment, DeploymentStatus
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.ports.session_port import SessionPort

class ExecuteLocalDeployment:
    def __init__(self, nix_port: NixPort, session_port: SessionPort):
        self.nix_port = nix_port
        self.session_port = session_port

    def execute(self, config_path: str, command: str, session_name: str) -> SessionId:
        """
        Orchestrates the local deployment process.
        """
        config = NixConfig(Path(config_path))
        session_id = SessionId(session_name)
        
        # 1. Create Deployment Entity
        deployment = Deployment(session_id=session_id, config=config)
        deployment.start_build()

        try:
            # 2. Build/Resolve Nix Environment (Side-effect)
            # In Phase 1 "Local", we might just be using nix-shell, but let's assume we "build" 
            # to verify integrity or get the hash.
            nix_hash = self.nix_port.build(str(config.path))
            deployment.complete_build(nix_hash)

            # 3. Ensure Session Exists
            if not self.session_port.list_sessions(): # simplistic check, real one checks specific ID
                 # logic improved below to check if specific session exists or generic list
                 pass
            
            # Create session if it doesn't exist. Adapter handle idempotency or we check first?
            # Adapter returns False if exists, which is fine.
            self.session_port.create_session(session_id)

            # 4. Run Command in Nix Shell inside Session
            # shell_cmd = nix-shell <path> --run '<command>'
            shell_cmd = self.nix_port.shell(str(config.path), command)
            
            success = self.session_port.run_command(session_id, shell_cmd)
            if not success:
                raise RuntimeError("Failed to send command to Tmux session")

            deployment.complete()
            return session_id

        except Exception as e:
            deployment.fail(str(e))
            raise e
