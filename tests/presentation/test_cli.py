"""Tests for CLI module."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from chimera.presentation.cli.cli import async_main


def _make_container(**overrides):
    """Create a mock container with sensible defaults."""
    container = MagicMock()
    container.deploy_fleet = MagicMock()
    container.deploy_fleet.execute = AsyncMock(return_value=True)
    container.rollback = MagicMock()
    container.rollback.execute = AsyncMock(return_value=True)
    container.execute_local = MagicMock()
    container.autonomous_loop = MagicMock()
    container.autonomous_loop.execute = AsyncMock(return_value=None)
    container.tmux_adapter = MagicMock()
    container.tmux_adapter.attach_command = AsyncMock(return_value="tmux attach -t s")
    for key, value in overrides.items():
        setattr(container, key, value)
    return container


class TestCLIHelp:
    """Test all help outputs (no adapter dependencies)."""

    @pytest.mark.asyncio
    async def test_no_command_prints_help(self, capsys):
        with patch("sys.argv", ["chimera"]):
            await async_main()
        captured = capsys.readouterr()
        assert "Autonomous Determinism Engine" in captured.out

    @pytest.mark.asyncio
    async def test_help_flag(self):
        with patch("sys.argv", ["chimera", "--help"]), \
             pytest.raises(SystemExit, match="0"):
            await async_main()

    @pytest.mark.asyncio
    async def test_run_help(self):
        with patch("sys.argv", ["chimera", "run", "--help"]), \
             pytest.raises(SystemExit, match="0"):
            await async_main()

    @pytest.mark.asyncio
    async def test_deploy_help(self):
        with patch("sys.argv", ["chimera", "deploy", "--help"]), \
             pytest.raises(SystemExit, match="0"):
            await async_main()

    @pytest.mark.asyncio
    async def test_watch_help(self):
        with patch("sys.argv", ["chimera", "watch", "--help"]), \
             pytest.raises(SystemExit, match="0"):
            await async_main()

    @pytest.mark.asyncio
    async def test_rollback_help(self):
        with patch("sys.argv", ["chimera", "rollback", "--help"]), \
             pytest.raises(SystemExit, match="0"):
            await async_main()

    @pytest.mark.asyncio
    async def test_mcp_help(self):
        with patch("sys.argv", ["chimera", "mcp", "--help"]), \
             pytest.raises(SystemExit, match="0"):
            await async_main()

    @pytest.mark.asyncio
    async def test_verbose_flag(self):
        with patch("sys.argv", ["chimera", "--verbose"]):
            await async_main()

    @pytest.mark.asyncio
    async def test_debug_flag(self):
        with patch("sys.argv", ["chimera", "--debug"]):
            await async_main()


class TestCLICommands:
    """Test CLI command execution with mocked composition root."""

    @pytest.mark.asyncio
    async def test_deploy_success(self, capsys, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.deploy_fleet.execute = AsyncMock(return_value=True)

        with patch("sys.argv", [
            "chimera", "deploy", "-t", "10.0.0.1",
            "-c", str(nix_file), "echo hi"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Successful" in captured.out

    @pytest.mark.asyncio
    async def test_deploy_failure(self, capsys, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.deploy_fleet.execute = AsyncMock(return_value=False)

        with patch("sys.argv", [
            "chimera", "deploy", "-t", "10.0.0.1",
            "-c", str(nix_file), "echo hi"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Failed" in captured.out

    @pytest.mark.asyncio
    async def test_rollback_success(self, capsys):
        container = _make_container()
        container.rollback.execute = AsyncMock(return_value=True)

        with patch("sys.argv", ["chimera", "rollback", "-t", "10.0.0.1"]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Rollback Successful" in captured.out

    @pytest.mark.asyncio
    async def test_rollback_failure(self, capsys):
        container = _make_container()
        container.rollback.execute = AsyncMock(return_value=False)

        with patch("sys.argv", ["chimera", "rollback", "-t", "10.0.0.1"]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Rollback Failed" in captured.out

    @pytest.mark.asyncio
    async def test_run_success(self, capsys, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")

        from chimera.domain.value_objects.session_id import SessionId

        container = _make_container()
        container.execute_local.execute = AsyncMock(
            return_value=SessionId("test-session")
        )

        with patch("sys.argv", [
            "chimera", "run", "-c", str(nix_file), "echo hi"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Deployment Successful" in captured.out

    @pytest.mark.asyncio
    async def test_run_file_not_found(self, capsys, tmp_path):
        container = _make_container()
        container.execute_local.execute = AsyncMock(
            side_effect=FileNotFoundError("config not found")
        )

        with patch("sys.argv", [
            "chimera", "run", "-c", "/nonexistent.nix", "echo hi"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "not found" in captured.out

    @pytest.mark.asyncio
    async def test_watch_once(self, capsys, tmp_path):
        nix_file = tmp_path / "default.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.autonomous_loop.execute = AsyncMock(return_value=None)

        with patch("sys.argv", [
            "chimera", "watch", "-t", "10.0.0.1",
            "-c", str(nix_file), "--once"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Autonomous Watch" in captured.out
