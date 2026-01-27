import unittest
import sys
import os
import time
from pathlib import Path
from typing import List

# Add project root to path
sys.path.append(str(Path(__file__).parent.absolute()))

from chimera.application.use_cases.autonomous_loop import AutonomousLoop
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash

class PassThroughNixAdapter(NixAdapter):
    def shell(self, path: str, command: str) -> str:
        # Bypass nix-shell for environment where it's not installed
        return command

class TestPhase3(unittest.TestCase):
    def setUp(self):
        self.nix_adapter = PassThroughNixAdapter() # Use stub for localhost verification
        self.fabric_adapter = FabricAdapter()
        # Pass None for session_port as it's not used in Phase 2/3 orchestration logic currently
        self.deploy_fleet = DeployFleet(self.nix_adapter, self.fabric_adapter, None) 
        self.autonomous_loop = AutonomousLoop(self.nix_adapter, self.fabric_adapter, self.deploy_fleet)
        
        # Create a dummy config file
        self.config_path = Path("default.nix")
        if not self.config_path.exists():
            self.config_path.touch()

    def tearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()
        # Clean up tracked file
        if os.path.exists("/tmp/chimera_current_hash"):
            os.remove("/tmp/chimera_current_hash")

    def test_autonomous_healing(self):
        # 1. Setup "Expected" State
        # NixAdapter returns a dummy hash "0000..."
        expected_hash = self.nix_adapter.build(str(self.config_path))
        
        target = "localhost"
        import getpass
        user = getpass.getuser()
        target = f"{user}@localhost"
        
        print(f"Testing autonomous healing on {target}...")

        # 2. Simulate Drift (Write WRONG hash to state file)
        # Using Fabric to write to /tmp/chimera_current_hash
        # Since we use localhost, we can also write locally.
        # But let's use the adapter to be sure.
        node = Node.parse(target)
        conn = self.fabric_adapter._get_connection(node)
        conn.run(f"echo 'DRIFTED_HASH' > /tmp/chimera_current_hash", hide=True)

        # Verify it is drifted
        actual_hash = self.fabric_adapter.get_current_hash(node)
        self.assertNotEqual(actual_hash, expected_hash, "System should be drifted")

        # 3. Run Autonomous Loop (Once)
        # It should detect drift and trigger healing.
        # Healing command in AutonomousLoop is: "echo '{expected_hash}' > /tmp/chimera_current_hash && echo 'Healed'"
        self.autonomous_loop.execute(
            str(self.config_path), 
            "chimera-auto-test", 
            [target], 
            run_once=True
        )

        # 4. Verify Healing
        # The file content should now match expected hash
        # Give time for async tmux command to execute
        time.sleep(2)
        actual_hash_post = self.fabric_adapter.get_current_hash(node)
        self.assertEqual(actual_hash_post, expected_hash, "System should be healed (congruent)")

if __name__ == '__main__':
    unittest.main()
