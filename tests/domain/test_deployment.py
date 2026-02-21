"""
Domain Layer Tests

Architectural Intent:
- Unit tests for domain models and logic
- No mocks needed - pure domain logic testing
- Tests verify business rules and invariants
"""

import pytest
from pathlib import Path
from chimera.domain.entities.deployment import (
    Deployment,
    DeploymentStatus,
    DeploymentStartedEvent,
    DeploymentCompletedEvent,
    DeploymentFailedEvent,
)
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.value_objects.session_id import SessionId
from chimera.domain.value_objects.nix_hash import NixHash


class TestDeployment:
    """Tests for Deployment aggregate root."""

    def test_create_pending_deployment(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))

        deployment = Deployment(session_id=session_id, config=config)

        assert deployment.status == DeploymentStatus.PENDING
        assert deployment.session_id == session_id
        assert deployment.config == config
        assert deployment.nix_hash is None
        assert deployment.error_message is None
        assert len(deployment.domain_events) == 0

    def test_start_build_transitions_to_building(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(session_id=session_id, config=config)

        started_deployment = deployment.start_build()

        assert started_deployment.status == DeploymentStatus.BUILDING
        assert started_deployment.session_id == deployment.session_id
        assert len(started_deployment.domain_events) == 1
        assert isinstance(started_deployment.domain_events[0], DeploymentStartedEvent)

    def test_start_build_only_from_pending(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(
            session_id=session_id, config=config, status=DeploymentStatus.BUILDING
        )

        with pytest.raises(ValueError, match="can only start from PENDING"):
            deployment.start_build()

    def test_complete_build_transitions_to_running(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(
            session_id=session_id, config=config, status=DeploymentStatus.BUILDING
        )
        nix_hash = NixHash("00000000000000000000000000000000")

        running_deployment = deployment.complete_build(nix_hash)

        assert running_deployment.status == DeploymentStatus.RUNNING
        assert running_deployment.nix_hash == nix_hash
        assert len(running_deployment.domain_events) == 1

    def test_complete_build_only_from_building(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(
            session_id=session_id, config=config, status=DeploymentStatus.PENDING
        )
        nix_hash = NixHash("00000000000000000000000000000000")

        with pytest.raises(ValueError, match="must be BUILDING"):
            deployment.complete_build(nix_hash)

    def test_complete_transitions_to_completed(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(
            session_id=session_id, config=config, status=DeploymentStatus.RUNNING
        )

        completed_deployment = deployment.complete()

        assert completed_deployment.status == DeploymentStatus.COMPLETED
        assert len(completed_deployment.domain_events) == 1
        assert isinstance(
            completed_deployment.domain_events[0], DeploymentCompletedEvent
        )

    def test_complete_only_from_running(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(
            session_id=session_id, config=config, status=DeploymentStatus.PENDING
        )

        with pytest.raises(ValueError, match="must be RUNNING"):
            deployment.complete()

    def test_fail_transitions_to_failed(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(
            session_id=session_id, config=config, status=DeploymentStatus.BUILDING
        )

        failed_deployment = deployment.fail("Build failed")

        assert failed_deployment.status == DeploymentStatus.FAILED
        assert failed_deployment.error_message == "Build failed"
        assert len(failed_deployment.domain_events) == 1
        assert isinstance(failed_deployment.domain_events[0], DeploymentFailedEvent)

    def test_full_lifecycle(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        nix_hash = NixHash("00000000000000000000000000000000")

        deployment = Deployment(session_id=session_id, config=config)
        deployment = deployment.start_build()
        deployment = deployment.complete_build(nix_hash)
        deployment = deployment.complete()

        assert deployment.status == DeploymentStatus.COMPLETED
        assert len(deployment.domain_events) == 3

    def test_domain_events_contain_correct_data(self):
        session_id = SessionId("test-session")
        config = NixConfig(Path("default.nix"))
        deployment = Deployment(session_id=session_id, config=config)
        deployment = deployment.start_build()

        event = deployment.domain_events[0]
        assert event.aggregate_id == "test-session"
        assert event.session_id == "test-session"
        assert event.config_path == "default.nix"
