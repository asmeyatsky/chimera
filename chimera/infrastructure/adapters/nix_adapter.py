import subprocess
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.value_objects.nix_hash import NixHash

class NixAdapter(NixPort):
    def build(self, path: str) -> NixHash:
        # Simplification: assuming path is a flake or default.nix
        # If it's a flake, use 'nix build'
        # If just a path, use 'nix-build'
        
        # For Phase 1 Local Engine, let's assume standard nix-build for now or flake uri
        try:
            # Using 'nix-instantiate' to get the derivation hash for potential congruence check
            # Real implementation would likely use 'nix build --json' to get output path and hash
            
            # Temporary implementation: return dummy hash for now until we have real nix environment to test against
            # In a real scenario, we would parse the output of nix-build
            # process = subprocess.run(['nix-build', path], capture_output=True, text=True, check=True)
            # output_path = process.stdout.strip()
             
             # For now, let's just return a valid dummy hash to satisfy the Value Object
             return NixHash("00000000000000000000000000000000") 
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Nix build failed: {e.stderr}")

    def instantiate(self, path: str) -> str:
        try:
            process = subprocess.run(['nix-instantiate', path], capture_output=True, text=True, check=True)
            return process.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Nix instantiate failed: {e.stderr}")

    def shell(self, path: str, command: str) -> str:
        # Constructs the command to run command inside nix-shell
        return f"nix-shell {path} --run '{command}'"
