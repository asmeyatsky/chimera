"""Integration tests for composition root wiring.

Verifies that all dependencies are correctly wired and use cases
can be invoked through the container.
"""

import pytest
from unittest.mock import patch, MagicMock

from chimera.composition_root import create_container, ChimeraContainer
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.application.use_cases.rollback_deployment import RollbackDeployment
from chimera.application.use_cases.execute_local_deployment import ExecuteLocalDeployment


class TestCompositionRootWiring:
    def test_container_types(self):
        container = create_container()
        assert isinstance(container.nix_adapter, NixAdapter)
        assert isinstance(container.fabric_adapter, FabricAdapter)
        assert isinstance(container.deploy_fleet, DeployFleet)
        assert isinstance(container.rollback, RollbackDeployment)
        assert isinstance(container.execute_local, ExecuteLocalDeployment)

    def test_shared_adapter_instances(self):
        """Use cases share the same adapter instances."""
        container = create_container()
        assert container.deploy_fleet.nix_port is container.nix_adapter
        assert container.deploy_fleet.remote_executor is container.fabric_adapter
        assert container.rollback.remote_executor is container.fabric_adapter
        assert container.execute_local.nix_port is container.nix_adapter

    @pytest.mark.asyncio
    async def test_deploy_via_container(self):
        """Invoke deploy through container with mocked I/O."""
        container = create_container()

        build_result = MagicMock()
        build_result.returncode = 0
        build_result.stdout = "/nix/store/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4-pkg"

        sync_result = MagicMock()
        sync_result.returncode = 0

        exec_result = MagicMock()
        exec_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): exec_result}

        with patch("subprocess.run") as mock_run, \
             patch("fabric.ThreadingGroup", return_value=mock_group):
            mock_run.side_effect = [build_result, sync_result]
            result = await container.deploy_fleet.execute(
                "default.nix", "echo hi", "session", ["10.0.0.1"]
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_rollback_via_container(self):
        """Invoke rollback through container."""
        container = create_container()

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await container.rollback.execute(["10.0.0.1"])

        assert result is True
