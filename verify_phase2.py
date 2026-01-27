import unittest
import sys
import os
from pathlib import Path
from typing import List

# Add project root to path
sys.path.append(str(Path(__file__).parent.absolute()))

from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.domain.value_objects.node import Node

class TestPhase2(unittest.TestCase):
    def setUp(self):
        self.nix_adapter = NixAdapter()
        self.fabric_adapter = FabricAdapter()
        # Pass None for session_port as it's not used in Phase 2 orchestration logic currently
        self.use_case = DeployFleet(self.nix_adapter, self.fabric_adapter, None) 
        
        # Create a dummy config file
        self.config_path = Path("default.nix")
        if not self.config_path.exists():
            self.config_path.touch()

    def tearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()

    def test_deploy_localhost(self):
        # This test requires SSH access to localhost.
        # It attempts to deploy a simple command.
        
        target = "localhost" # Assumes current user, port 22
        # If user is different or port is different, it might fail.
        # We can try to detect current user.
        import getpass
        user = getpass.getuser()
        target = f"{user}@localhost"
        
        print(f"Attempting deployment to {target}...")
        
        # Command: simple echo
        success = self.use_case.execute(
            str(self.config_path), 
            "echo 'Phase 2 Verified' > /tmp/chimera_phase2.txt", 
            "chimera-p2-test", 
            [target]
        )
        
        self.assertTrue(success, "Deployment to localhost should succeed")
        
        # Verify side effect: check if file exists
        self.assertTrue(os.path.exists("/tmp/chimera_phase2.txt"))
        
        # Cleanup
        if os.path.exists("/tmp/chimera_phase2.txt"):
            os.remove("/tmp/chimera_phase2.txt")

if __name__ == '__main__':
    unittest.main()
