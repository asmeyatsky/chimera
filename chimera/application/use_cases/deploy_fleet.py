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
    def __init__(self, 
                 nix_port: NixPort, 
                 remote_executor: RemoteExecutorPort,
                 session_port: SessionPort): 
                 # session_port is local, usually. 
                 # For remote Tmux, we need RemoteExecutor to execute Tmux commands Remotely.
                 # The current SessionPort assumes local subprocess.
                 # We might need a RemoteTmuxAdapter, or adapt SessionPort to work over an executor.
                 # Or here we just use remote_executor directly for Tmux commands.
                 # Given "Convergence", let's use the executor to send tmux commands.
        self.nix_port = nix_port
        self.remote_executor = remote_executor
        # self.session_port = session_port # Not used for remote unless adapted

    def execute(self, config_path: str, command: str, session_name: str, targets: List[str]) -> bool:
        """
        Orchestrates fleet deployment.
        """
        config = NixConfig(Path(config_path))
        nodes = [Node.parse(t) for t in targets]
        
        # 1. Build Local (get closure hash)
        # In a real scenario, we build locally first.
        try:
            nix_hash = self.nix_port.build(str(config.path))
        except Exception as e:
            print(f"Build failed: {e}")
            return False

        # 2. Sync Closure to Nodes
        if not self.remote_executor.sync_closure(nodes, str(nix_hash)): # or path?
             print("Sync failed")
             return False

        # 3. Ensure Tmux Session on Nodes
        # tmux new-session -d -s name || true
        # Use full path to avoid PATH issues in non-interactive shells
        tmux_cmd = "/usr/local/bin/tmux"
        session_cmd = f"{tmux_cmd} new-session -d -s {session_name} || true"
        if not self.remote_executor.exec_command(nodes, session_cmd):
            print("Session creation failed")
            return False

        # 4. Execute Command in Nix Shell in Remote Tmux
        
        cmd_to_send = self.nix_port.shell(str(config.path), command)
        
        tmux_send = f"{tmux_cmd} send-keys -t {session_name} '{cmd_to_send}' C-m"
        
        if not self.remote_executor.exec_command(nodes, tmux_send):
            print("Command execution failed")
            return False
            
        print(f"Deployment successful to {len(nodes)} nodes.")
        return True
