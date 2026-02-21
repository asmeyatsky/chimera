"""
Deployment Module

Architectural Intent:
- Deployment aggregate is the consistency boundary for all deployment operations
- Deployment lifecycle managed through state transitions enforced by domain methods
- All state changes produce new instances to ensure auditability
- Domain events published for cross-context communication (e.g., notifications, monitoring)
- External Nix and Session capabilities abstracted behind ports

Domain Events:
- DeploymentStartedEvent: Published when a deployment begins
- DeploymentCompletedEvent: Published when deployment succeeds
- DeploymentFailedEvent: Published when deployment fails
"""

from __future__ import annotations
from datetime import datetime, UTC
from enum import Enum, auto
from typing import Optional, Any
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.entities.nix_config import NixConfig


class DeploymentStatus(Enum):
    PENDING = auto()
    BUILDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class DomainEvent:
    def __init__(self, aggregate_id: str) -> None:
        self._aggregate_id = aggregate_id
        self._occurred_at = datetime.now(UTC).isoformat()

    @property
    def aggregate_id(self) -> str:
        return self._aggregate_id

    @property
    def occurred_at(self) -> str:
        return self._occurred_at

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at,
            "event_type": self.event_type,
        }


class DeploymentStartedEvent(DomainEvent):
    def __init__(self, aggregate_id: str, session_id: str, config_path: str) -> None:
        super().__init__(aggregate_id)
        self._session_id = session_id
        self._config_path = config_path

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def config_path(self) -> str:
        return self._config_path


class DeploymentBuildCompletedEvent(DomainEvent):
    def __init__(self, aggregate_id: str, session_id: str, nix_hash: str) -> None:
        super().__init__(aggregate_id)
        self._session_id = session_id
        self._nix_hash = nix_hash

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def nix_hash(self) -> str:
        return self._nix_hash


class DeploymentCompletedEvent(DomainEvent):
    def __init__(self, aggregate_id: str, session_id: str) -> None:
        super().__init__(aggregate_id)
        self._session_id = session_id

    @property
    def session_id(self) -> str:
        return self._session_id


class DeploymentFailedEvent(DomainEvent):
    def __init__(self, aggregate_id: str, session_id: str, error_message: str) -> None:
        super().__init__(aggregate_id)
        self._session_id = session_id
        self._error_message = error_message

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def error_message(self) -> str:
        return self._error_message


class Deployment:
    __slots__ = (
        "_session_id",
        "_config",
        "_status",
        "_nix_hash",
        "_error_message",
        "_domain_events",
    )

    def __init__(
        self,
        session_id: SessionId,
        config: NixConfig,
        status: DeploymentStatus = DeploymentStatus.PENDING,
        nix_hash: Optional[NixHash] = None,
        error_message: Optional[str] = None,
        domain_events: tuple = (),
    ):
        self._session_id = session_id
        self._config = config
        self._status = status
        self._nix_hash = nix_hash
        self._error_message = error_message
        self._domain_events = domain_events

    @property
    def session_id(self) -> SessionId:
        return self._session_id

    @property
    def config(self) -> NixConfig:
        return self._config

    @property
    def status(self) -> DeploymentStatus:
        return self._status

    @property
    def nix_hash(self) -> Optional[NixHash]:
        return self._nix_hash

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @property
    def domain_events(self) -> tuple:
        return self._domain_events

    def start_build(self) -> "Deployment":
        if self._status != DeploymentStatus.PENDING:
            raise ValueError("Deployment can only start from PENDING state")
        return Deployment(
            session_id=self._session_id,
            config=self._config,
            status=DeploymentStatus.BUILDING,
            nix_hash=self._nix_hash,
            error_message=self._error_message,
            domain_events=self._domain_events
            + (
                DeploymentStartedEvent(
                    aggregate_id=str(self._session_id),
                    session_id=str(self._session_id),
                    config_path=str(self._config.path),
                ),
            ),
        )

    def complete_build(self, nix_hash: NixHash) -> "Deployment":
        if self._status != DeploymentStatus.BUILDING:
            raise ValueError("Deployment must be BUILDING to complete build")
        return Deployment(
            session_id=self._session_id,
            config=self._config,
            status=DeploymentStatus.RUNNING,
            nix_hash=nix_hash,
            error_message=self._error_message,
            domain_events=self._domain_events
            + (
                DeploymentBuildCompletedEvent(
                    aggregate_id=str(self._session_id),
                    session_id=str(self._session_id),
                    nix_hash=str(nix_hash),
                ),
            ),
        )

    def fail(self, message: str) -> "Deployment":
        return Deployment(
            session_id=self._session_id,
            config=self._config,
            status=DeploymentStatus.FAILED,
            nix_hash=self._nix_hash,
            error_message=message,
            domain_events=self._domain_events
            + (
                DeploymentFailedEvent(
                    aggregate_id=str(self._session_id),
                    session_id=str(self._session_id),
                    error_message=message,
                ),
            ),
        )

    def complete(self) -> "Deployment":
        if self._status != DeploymentStatus.RUNNING:
            raise ValueError("Deployment must be RUNNING to complete")
        return Deployment(
            session_id=self._session_id,
            config=self._config,
            status=DeploymentStatus.COMPLETED,
            nix_hash=self._nix_hash,
            error_message=self._error_message,
            domain_events=self._domain_events
            + (
                DeploymentCompletedEvent(
                    aggregate_id=str(self._session_id),
                    session_id=str(self._session_id),
                ),
            ),
        )

    def __repr__(self) -> str:
        return (
            f"Deployment(session_id={self._session_id}, "
            f"config={self._config}, status={self._status}, "
            f"nix_hash={self._nix_hash}, error_message={self._error_message})"
        )
