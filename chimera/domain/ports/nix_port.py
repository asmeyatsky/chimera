"""
Nix Port

Architectural Intent:
- Port interface for interacting with Nix ecosystem
- Abstracts Nix build, instantiate, and shell commands
- Implemented by NixAdapter or MCP-based adapters
"""

from abc import ABC, abstractmethod
from chimera.domain.value_objects.nix_hash import NixHash


class NixPort(ABC):
    """
    Port interface for interacting with Nix ecosystem.
    """

    @abstractmethod
    async def build(self, path: str) -> NixHash:
        """
        Builds a Nix derivation and returns its hash.
        """
        pass

    @abstractmethod
    async def instantiate(self, path: str) -> str:
        """
        Instantiates a Nix expression to a store path.
        """
        pass

    @abstractmethod
    async def shell(self, path: str, command: str) -> str:
        """
        Constructs a command to run within a nix-shell.
        """
        pass
