"""Tests for composition root DI container."""

import pytest


class TestCompositionRoot:
    def test_create_container(self):
        from chimera.composition_root import create_container, ChimeraContainer

        container = create_container()

        assert isinstance(container, ChimeraContainer)
        assert container.nix_adapter is not None
        assert container.tmux_adapter is not None
        assert container.fabric_adapter is not None
        assert container.event_bus is not None
        assert container.deploy_fleet is not None
        assert container.execute_local is not None
        assert container.rollback is not None
        assert container.autonomous_loop is not None

    def test_deploy_fleet_uses_nix_and_fabric(self):
        from chimera.composition_root import create_container

        container = create_container()

        assert container.deploy_fleet.nix_port is container.nix_adapter
        assert container.deploy_fleet.remote_executor is container.fabric_adapter

    def test_autonomous_loop_uses_deploy_fleet(self):
        from chimera.composition_root import create_container

        container = create_container()

        assert container.autonomous_loop.deploy_fleet is container.deploy_fleet
