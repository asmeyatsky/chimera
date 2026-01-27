from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.entities.nix_config import NixConfig

class DeploymentStatus(Enum):
    PENDING = auto()
    BUILDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class Deployment:
    """
    Aggregate Root representing a deployment process.
    """
    session_id: SessionId
    config: NixConfig
    status: DeploymentStatus = field(default=DeploymentStatus.PENDING)
    nix_hash: Optional[NixHash] = None
    error_message: Optional[str] = None

    def start_build(self):
        if self.status != DeploymentStatus.PENDING:
            raise ValueError("Deployment can only start from PENDING state")
        self.status = DeploymentStatus.BUILDING

    def complete_build(self, nix_hash: NixHash):
        if self.status != DeploymentStatus.BUILDING:
            raise ValueError("Deployment must be BUILDING to complete build")
        self.nix_hash = nix_hash
        self.status = DeploymentStatus.RUNNING

    def fail(self, message: str):
        self.status = DeploymentStatus.FAILED
        self.error_message = message

    def complete(self):
        if self.status != DeploymentStatus.RUNNING:
            raise ValueError("Deployment must be RUNNING to complete")
        self.status = DeploymentStatus.COMPLETED
