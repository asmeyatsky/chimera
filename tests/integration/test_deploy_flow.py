"""Integration tests for deployment flows.

These tests wire real use cases with real adapters, mocking only
external I/O (subprocess, SSH connections).
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.application.use_cases.rollback_deployment import RollbackDeployment
from chimera.domain.value_objects.nix_hash import NixHash


class TestDeployFleetIntegration:
    """End-to-end deploy flow with real wiring, mocked subprocess/SSH."""

    @pytest.mark.asyncio
    async def test_full_deploy_success(self):
        """Build -> sync -> session -> execute, all succeed."""
        nix = NixAdapter()
        fabric = FabricAdapter()
        use_case = DeployFleet(nix, fabric)

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
            # First call = nix-build, subsequent = nix-copy-closure
            mock_run.side_effect = [build_result, sync_result]

            result = await use_case.execute(
                "default.nix", "echo hello", "test-session", ["10.0.0.1"]
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_deploy_build_failure_aborts(self):
        """If nix-build fails, whole deploy fails."""
        import subprocess as sp

        nix = NixAdapter()
        fabric = FabricAdapter()
        use_case = DeployFleet(nix, fabric)

        with patch(
            "subprocess.run",
            side_effect=sp.CalledProcessError(1, "nix-build", stderr="build error"),
        ):
            result = await use_case.execute(
                "default.nix", "echo hello", "test-session", ["10.0.0.1"]
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_deploy_sync_failure_aborts(self):
        """If sync fails, deploy fails without executing."""
        nix = NixAdapter()
        fabric = FabricAdapter()
        use_case = DeployFleet(nix, fabric)

        build_result = MagicMock()
        build_result.returncode = 0
        build_result.stdout = "/nix/store/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4-pkg"

        sync_result = MagicMock()
        sync_result.returncode = 1
        sync_result.stderr = "sync failed"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [build_result, sync_result]

            result = await use_case.execute(
                "default.nix", "echo hello", "test-session", ["10.0.0.1"]
            )

        assert result is False


class TestRollbackIntegration:
    """End-to-end rollback flow."""

    @pytest.mark.asyncio
    async def test_rollback_success(self):
        fabric = FabricAdapter()
        use_case = RollbackDeployment(fabric)

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await use_case.execute(["10.0.0.1"])

        assert result is True

    @pytest.mark.asyncio
    async def test_rollback_with_generation(self):
        fabric = FabricAdapter()
        use_case = RollbackDeployment(fabric)

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await use_case.execute(["10.0.0.1"], generation="42")

        assert result is True
        call_args = mock_group.run.call_args
        assert "42" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_rollback_multi_node(self):
        fabric = FabricAdapter()
        use_case = RollbackDeployment(fabric)

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group) as mock_tg:
            result = await use_case.execute(["10.0.0.1", "10.0.0.2"])

        assert result is True
        # Verify both hosts were included
        hosts_arg = mock_tg.call_args[0]
        assert len(hosts_arg) == 2
