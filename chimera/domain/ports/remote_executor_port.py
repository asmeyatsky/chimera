from abc import ABC, abstractmethod
from typing import List, Optional
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash

class RemoteExecutorPort(ABC):
    """
    Port interface for executing commands on remote infrastructure.
    """

    @abstractmethod
    def sync_closure(self, nodes: List[Node], closure_path: str) -> bool:
        """
        Syncs a Nix closure to a list of nodes.
        Returns True if successful for all nodes.
        """
        pass

    @abstractmethod
    def exec_command(self, nodes: List[Node], command: str) -> bool:
        """
        Executes a command on a list of nodes concurrently.
        Returns True if successful for all nodes.
        """
        pass

    @abstractmethod
    def get_current_hash(self, node: Node) -> Optional[NixHash]:
        """
        Retrieves the current Nix hash of the deployed system on a node.
        Returns None if not found or error.
        """
        pass

    @abstractmethod
    def rollback(self, nodes: List[Node], generation: Optional[str] = None) -> bool:
        """
        Rolls back the deployment on a list of nodes.
        If generation is None, rolls back one generation.
        """
        pass
