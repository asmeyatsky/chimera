"""Tests for DeployFleet use case."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.domain.value_objects.nix_hash import NixHash


class TestDeployFleet:
    def _make_use_case(self):
        nix_port = AsyncMock()
        nix_port.build = AsyncMock(
            return_value=NixHash("00000000000000000000000000000000")
        )
        nix_port.shell = AsyncMock(return_value="nix-shell default.nix --run 'echo hi'")
        remote_executor = AsyncMock()
        remote_executor.sync_closure = AsyncMock(return_value=True)
        remote_executor.exec_command = AsyncMock(return_value=True)
        return DeployFleet(nix_port, remote_executor), nix_port, remote_executor

    @pytest.mark.asyncio
    async def test_successful_deployment(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, remote = self._make_use_case()

        result = await use_case.execute(
            str(nix_file), "echo hi", "test-session", ["example.com"]
        )

        assert result is True
        nix_port.build.assert_awaited_once()
        assert remote.sync_closure.await_count == 1
        assert remote.exec_command.await_count == 2  # session + execute

    @pytest.mark.asyncio
    async def test_build_failure(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, remote = self._make_use_case()
        nix_port.build = AsyncMock(side_effect=RuntimeError("build failed"))

        result = await use_case.execute(
            str(nix_file), "echo hi", "test-session", ["example.com"]
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_sync_failure(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, remote = self._make_use_case()
        remote.sync_closure = AsyncMock(side_effect=RuntimeError("sync failed"))

        result = await use_case.execute(
            str(nix_file), "echo hi", "test-session", ["example.com"]
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_config_not_found(self):
        use_case, _, _ = self._make_use_case()

        with pytest.raises(FileNotFoundError):
            await use_case.execute(
                "/nonexistent.nix", "echo hi", "test-session", ["example.com"]
            )
