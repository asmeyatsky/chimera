import unittest
import sys
import time
from pathlib import Path
import libtmux

# Add project root to path
sys.path.append(str(Path(__file__).parent.absolute()))

from chimera.application.use_cases.execute_local_deployment import ExecuteLocalDeployment
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.domain.value_objects.session_id import SessionId

class TestPhase1(unittest.TestCase):
    def setUp(self):
        self.nix_adapter = NixAdapter()
        self.tmux_adapter = TmuxAdapter()
        self.use_case = ExecuteLocalDeployment(self.nix_adapter, self.tmux_adapter)
        
        # Create a dummy config file for validation
        self.config_path = Path("default.nix")
        self.config_path.touch()
        self.session_name = "chimera-verify-p1"
        self.cleanup_session()

    def tearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()
        self.cleanup_session()

    def cleanup_session(self):
        # Clean up tmux session if exists
        try:
            server = libtmux.Server()
            if server.has_session(self.session_name):
                server.kill_session(self.session_name)
        except Exception:
            pass

    def test_execute_local_deployment_real(self):
        # Should create a real tmux session
        session_id = self.use_case.execute(str(self.config_path), "echo 'Hello Chimera' > /tmp/chimera_test.txt", self.session_name)

        self.assertEqual(str(session_id), self.session_name)
        
        # Verify Session Exists
        server = libtmux.Server()
        self.assertTrue(server.has_session(self.session_name))
        
        # Optional: Verify command ran (Wait a bit for tmux to process)
        # Note: nix-shell might fail if nix is not installed, but TmuxAdapter functionality is what we verify here primarily for Phase 1 "Engine"
        # The command in ExecuteLocalDeployment wraps in nix-shell. 
        # If nix-shell fails, it might exit the shell, but the window should stay or session might close if it was spawned with a command that exited.
        # But we create_session first (which spawns a shell), then send_keys. 
        # So session should persist with the shell.
        
        time.sleep(1)
        session = server.sessions.get(session_name=self.session_name)
        self.assertIsNotNone(session)

if __name__ == '__main__':
    unittest.main()
