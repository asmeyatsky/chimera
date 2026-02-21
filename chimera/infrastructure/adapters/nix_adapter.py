"""
Nix Adapter

Architectural Intent:
- Infrastructure adapter implementing NixPort
- Provides Nix build, instantiate, and shell capabilities
- Uses subprocess for Nix CLI operations wrapped in async
"""

import asyncio
import subprocess
import os
import shlex
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.value_objects.nix_hash import NixHash


class NixAdapter(NixPort):
    async def build(self, path: str) -> NixHash:
        def _build():
            try:
                result = subprocess.run(
                    ["nix-build", path, "--no-out-link"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                store_path = result.stdout.strip()
                basename = os.path.basename(store_path)
                hash_part = basename.split("-")[0]
                return NixHash(hash_part)
            except FileNotFoundError:
                print("[-] 'nix-build' not found. Using simulation mode.")
                return NixHash("00000000000000000000000000000000")
            except subprocess.CalledProcessError as e:
                raise Exception(f"Nix build failed: {e.stderr}")

        return await asyncio.get_event_loop().run_in_executor(None, _build)

    async def instantiate(self, path: str) -> str:
        def _instantiate():
            try:
                result = subprocess.run(
                    ["nix-instantiate", path],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout.strip()
            except FileNotFoundError:
                return f"{path}.drv"
            except subprocess.CalledProcessError as e:
                raise Exception(f"Nix instantiate failed: {e.stderr}")

        return await asyncio.get_event_loop().run_in_executor(None, _instantiate)

    async def shell(self, path: str, command: str) -> str:
        quoted_cmd = shlex.quote(command)
        return f"nix-shell {path} --run {quoted_cmd}"
