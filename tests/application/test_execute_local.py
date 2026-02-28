"""Tests for ExecuteLocalDeployment use case."""

import pytest
from unittest.mock import AsyncMock
from chimera.application.use_cases.execute_local_deployment import ExecuteLocalDeployment
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.value_objects.session_id import SessionId


class TestExecuteLocalDeployment:
    def _make_use_case(self):
        nix_port = AsyncMock()
        nix_port.build = AsyncMock(
            return_value=NixHash("00000000000000000000000000000000")
        )
        nix_port.shell = AsyncMock(return_value="nix-shell default.nix --run 'echo hi'")
        session_port = AsyncMock()
        session_port.create_session = AsyncMock(return_value=True)
        session_port.run_command = AsyncMock(return_value=True)
        return ExecuteLocalDeployment(nix_port, session_port), nix_port, session_port

    @pytest.mark.asyncio
    async def test_successful_deployment(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, session_port = self._make_use_case()

        session_id = await use_case.execute(
            str(nix_file), "echo hi", "test-session"
        )

        assert isinstance(session_id, SessionId)
        assert str(session_id) == "test-session"
        nix_port.build.assert_awaited_once()
        session_port.create_session.assert_awaited_once()
        session_port.run_command.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_build_failure(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, session_port = self._make_use_case()
        nix_port.build = AsyncMock(side_effect=RuntimeError("build failed"))

        with pytest.raises(RuntimeError, match="build failed"):
            await use_case.execute(str(nix_file), "echo hi", "test-session")

    @pytest.mark.asyncio
    async def test_run_command_failure(self, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")
        use_case, nix_port, session_port = self._make_use_case()
        session_port.run_command = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="Failed to send command"):
            await use_case.execute(str(nix_file), "echo hi", "test-session")

    @pytest.mark.asyncio
    async def test_config_not_found(self):
        use_case, _, _ = self._make_use_case()

        with pytest.raises(FileNotFoundError):
            await use_case.execute("/nonexistent.nix", "echo hi", "test-session")
