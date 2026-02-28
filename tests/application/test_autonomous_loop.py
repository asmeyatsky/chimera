"""Tests for AutonomousLoop use case."""

import pytest
from unittest.mock import AsyncMock, patch
from chimera.application.use_cases.autonomous_loop import AutonomousLoop
from chimera.domain.value_objects.nix_hash import NixHash


class TestAutonomousLoop:
    def _make_use_case(self):
        nix_port = AsyncMock()
        nix_port.build = AsyncMock(
            return_value=NixHash("00000000000000000000000000000000")
        )
        remote = AsyncMock()
        deploy_fleet = AsyncMock()
        deploy_fleet.execute = AsyncMock(return_value=True)
        return (
            AutonomousLoop(nix_port, remote, deploy_fleet),
            nix_port,
            remote,
            deploy_fleet,
        )

    @pytest.mark.asyncio
    async def test_congruent_fleet_no_healing(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, remote, deploy = self._make_use_case()
        remote.get_current_hash = AsyncMock(
            return_value=NixHash("00000000000000000000000000000000")
        )

        await use_case.execute(
            str(nix_file), "test-session", ["example.com"],
            interval_seconds=1, run_once=True,
        )

        deploy.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_drifted_node_triggers_healing(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, remote, deploy = self._make_use_case()
        remote.get_current_hash = AsyncMock(
            return_value=NixHash("11111111111111111111111111111111")
        )

        await use_case.execute(
            str(nix_file), "test-session", ["example.com"],
            interval_seconds=1, run_once=True,
        )

        deploy.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_build_failure_aborts(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, remote, deploy = self._make_use_case()
        nix_port.build = AsyncMock(side_effect=RuntimeError("fail"))

        await use_case.execute(
            str(nix_file), "test-session", ["example.com"],
            interval_seconds=1, run_once=True,
        )

        deploy.execute.assert_not_awaited()
