from abc import ABC, abstractmethod
from chimera.domain.value_objects.nix_hash import NixHash

class NixPort(ABC):
    """
    Port interface for interacting with Nix ecosystem.
    """
    
    @abstractmethod
    def build(self, path: str) -> NixHash:
        """
        Builds a Nix derivation and returns its hash.
        """
        pass

    @abstractmethod
    def instantiate(self, path: str) -> str:
        """
        Instantiates a Nix expression to a store path.
        """
        pass

    @abstractmethod
    def shell(self, path: str, command: str) -> str:
        """
        Constructs a command to run within a nix-shell.
        """
        pass
