"""
Nix Port

Architectural Intent:
- Port interface for interacting with Nix ecosystem
- Abstracts Nix build, instantiate, and shell commands
- Implemented by NixAdapter or MCP-based adapters
"""

from typing import Protocol, runtime_checkable
from chimera.domain.value_objects.nix_hash import NixHash


@runtime_checkable
class NixPort(Protocol):
    """Port interface for interacting with Nix ecosystem."""

    async def build(self, path: str) -> NixHash: ...

    async def instantiate(self, path: str) -> str: ...

    async def shell(self, path: str, command: str) -> str: ...
