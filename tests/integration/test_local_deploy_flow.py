"""Integration tests for local deployment flow.

Wires real NixAdapter + TmuxAdapter with mocked subprocess/libtmux.
"""

import pytest
from unittest.mock import patch, MagicMock

from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.application.use_cases.execute_local_deployment import (
    ExecuteLocalDeployment,
)
from chimera.domain.value_objects.session_id import SessionId


class TestLocalDeployIntegration:
    @pytest.mark.asyncio
    async def test_full_local_deploy(self):
        """Build -> create session -> run command, all succeed."""
        nix = NixAdapter()
        tmux = TmuxAdapter()
        use_case = ExecuteLocalDeployment(nix, tmux)

        build_result = MagicMock()
        build_result.returncode = 0
        build_result.stdout = "/nix/store/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4-pkg"

        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_window = MagicMock()
        mock_pane = MagicMock()
        mock_session.attached_window = mock_window
        mock_window.attached_pane = mock_pane

        mock_server = MagicMock()
        mock_server.sessions.get.return_value = mock_session
        mock_server.new_session.return_value = mock_session
        mock_server.has_session.return_value = False
        tmux.server = mock_server

        with patch("subprocess.run", return_value=build_result):
            session_id = await use_case.execute(
                "default.nix", "echo hello", "test-session"
            )

        assert isinstance(session_id, SessionId)
        assert str(session_id) == "test-session"

    @pytest.mark.asyncio
    async def test_local_deploy_build_failure(self):
        """If nix-build fails, deployment fails."""
        import subprocess as sp

        nix = NixAdapter()
        tmux = TmuxAdapter()
        use_case = ExecuteLocalDeployment(nix, tmux)

        with patch(
            "subprocess.run",
            side_effect=sp.CalledProcessError(1, "nix-build", stderr="error"),
        ):
            with pytest.raises(Exception, match="Nix build failed"):
                await use_case.execute("default.nix", "echo hello", "test-session")
