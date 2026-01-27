from dataclasses import dataclass
from typing import Optional
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash

@dataclass(frozen=True)
class CongruenceReport:
    """
    Value Object representing the congruence status of a node.
    """
    node: Node
    expected_hash: NixHash
    actual_hash: Optional[NixHash]
    is_congruent: bool
    details: str = ""

    @staticmethod
    def congruent(node: Node, hash_val: NixHash) -> 'CongruenceReport':
        return CongruenceReport(
            node=node,
            expected_hash=hash_val,
            actual_hash=hash_val,
            is_congruent=True,
            details="System state matches expected configuration."
        )

    @staticmethod
    def drift(node: Node, expected: NixHash, actual: Optional[NixHash], details: str) -> 'CongruenceReport':
        return CongruenceReport(
            node=node,
            expected_hash=expected,
            actual_hash=actual,
            is_congruent=False,
            details=details
        )
