import subprocess
import os
import shlex
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.value_objects.nix_hash import NixHash

class NixAdapter(NixPort):
    def build(self, path: str) -> NixHash:
        """
        Builds a Nix expression and returns the store path hash.
        """
        try:
            # Command: nix-build <path> --no-out-link
            result = subprocess.run(
                ["nix-build", path, "--no-out-link"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            store_path = result.stdout.strip()
            # Extract hash (32 chars after /nix/store/)
            basename = os.path.basename(store_path)
            hash_part = basename.split("-")[0]
            
            return NixHash(hash_part)
            
        except FileNotFoundError:
            print("[-] 'nix-build' not found. Using simulation mode.")
            return NixHash("00000000000000000000000000000000")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Nix build failed: {e.stderr}")

    def instantiate(self, path: str) -> str:
        """
        Instantiates a Nix expression.
        """
        try:
            result = subprocess.run(
                ["nix-instantiate", path],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return f"{path}.drv"
        except subprocess.CalledProcessError as e:
             raise Exception(f"Nix instantiate failed: {e.stderr}")

    def shell(self, path: str, command: str) -> str:
        """
        Returns a command string to run 'command' inside a nix-shell for 'path'.
        """
        quoted_cmd = shlex.quote(command)
        return f"nix-shell {path} --run {quoted_cmd}"
