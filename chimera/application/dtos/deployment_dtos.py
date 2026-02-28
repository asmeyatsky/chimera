"""
Deployment DTOs

Architectural Intent:
- Data Transfer Objects for deployment use case boundaries
- Input validation at the application boundary
- Decouples external representation from domain model
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DeployFleetRequest:
    config_path: str
    command: str
    session_name: str
    targets: list[str]

    def __post_init__(self) -> None:
        if not self.config_path:
            raise ValueError("config_path cannot be empty")
        if not self.command:
            raise ValueError("command cannot be empty")
        if not self.session_name:
            raise ValueError("session_name cannot be empty")
        if not self.targets:
            raise ValueError("targets cannot be empty")


@dataclass(frozen=True)
class DeployFleetResponse:
    success: bool
    message: str
    nodes_deployed: int = 0


@dataclass(frozen=True)
class RollbackRequest:
    targets: list[str]
    generation: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("targets cannot be empty")


@dataclass(frozen=True)
class RollbackResponse:
    success: bool
    message: str


@dataclass(frozen=True)
class LocalDeploymentRequest:
    config_path: str
    command: str
    session_name: str

    def __post_init__(self) -> None:
        if not self.config_path:
            raise ValueError("config_path cannot be empty")
        if not self.command:
            raise ValueError("command cannot be empty")
        if not self.session_name:
            raise ValueError("session_name cannot be empty")


@dataclass(frozen=True)
class LocalDeploymentResponse:
    success: bool
    session_id: str
    message: str = ""
