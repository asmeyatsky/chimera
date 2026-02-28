"""
Deployment Module

Architectural Intent:
- Deployment aggregate is the consistency boundary for all deployment operations
- Deployment lifecycle managed through state transitions enforced by domain methods
- All state changes produce new frozen instances to ensure immutability and auditability
- Domain events published for cross-context communication (e.g., notifications, monitoring)
- External Nix and Session capabilities abstracted behind ports

Domain Events:
- DeploymentStartedEvent: Published when a deployment begins
- DeploymentCompletedEvent: Published when deployment succeeds
- DeploymentFailedEvent: Published when deployment fails

Design Decisions:
- Uses frozen dataclass for immutability
- State transitions return new instances (not mutations)
- Events accumulated as a tuple for append-only semantics
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto
from typing import Optional, Any
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.events.event_base import DomainEvent


class DeploymentStatus(Enum):
    PENDING = auto()
    BUILDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class DeploymentStartedEvent(DomainEvent):
    session_id: str = ""
    config_path: str = ""


@dataclass(frozen=True)
class DeploymentBuildCompletedEvent(DomainEvent):
    session_id: str = ""
    nix_hash: str = ""


@dataclass(frozen=True)
class DeploymentCompletedEvent(DomainEvent):
    session_id: str = ""


@dataclass(frozen=True)
class DeploymentFailedEvent(DomainEvent):
    session_id: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class Deployment:
    """Deployment aggregate root. Immutable — state transitions return new instances."""

    session_id: SessionId
    config: NixConfig
    status: DeploymentStatus = DeploymentStatus.PENDING
    nix_hash: Optional[NixHash] = None
    error_message: Optional[str] = None
    domain_events: tuple = ()

    def start_build(self) -> Deployment:
        if self.status != DeploymentStatus.PENDING:
            raise ValueError("Deployment can only start from PENDING state")
        return Deployment(
            session_id=self.session_id,
            config=self.config,
            status=DeploymentStatus.BUILDING,
            nix_hash=self.nix_hash,
            error_message=self.error_message,
            domain_events=self.domain_events
            + (
                DeploymentStartedEvent(
                    aggregate_id=str(self.session_id),
                    session_id=str(self.session_id),
                    config_path=str(self.config.path),
                ),
            ),
        )

    def complete_build(self, nix_hash: NixHash) -> Deployment:
        if self.status != DeploymentStatus.BUILDING:
            raise ValueError("Deployment must be BUILDING to complete build")
        return Deployment(
            session_id=self.session_id,
            config=self.config,
            status=DeploymentStatus.RUNNING,
            nix_hash=nix_hash,
            error_message=self.error_message,
            domain_events=self.domain_events
            + (
                DeploymentBuildCompletedEvent(
                    aggregate_id=str(self.session_id),
                    session_id=str(self.session_id),
                    nix_hash=str(nix_hash),
                ),
            ),
        )

    def fail(self, message: str) -> Deployment:
        return Deployment(
            session_id=self.session_id,
            config=self.config,
            status=DeploymentStatus.FAILED,
            nix_hash=self.nix_hash,
            error_message=message,
            domain_events=self.domain_events
            + (
                DeploymentFailedEvent(
                    aggregate_id=str(self.session_id),
                    session_id=str(self.session_id),
                    error_message=message,
                ),
            ),
        )

    def complete(self) -> Deployment:
        if self.status != DeploymentStatus.RUNNING:
            raise ValueError("Deployment must be RUNNING to complete")
        return Deployment(
            session_id=self.session_id,
            config=self.config,
            status=DeploymentStatus.COMPLETED,
            nix_hash=self.nix_hash,
            error_message=self.error_message,
            domain_events=self.domain_events
            + (
                DeploymentCompletedEvent(
                    aggregate_id=str(self.session_id),
                    session_id=str(self.session_id),
                ),
            ),
        )
