"""End-to-end tests for the Chimera CLI.

Tests the full flow from CLI invocation through to mocked infrastructure,
exercising argument parsing, composition root wiring, use case dispatch,
and output formatting as a single integrated path.
"""

import json
import os
import subprocess
import sys

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from chimera.presentation.cli.cli import async_main
from chimera.domain.value_objects.session_id import SessionId
from chimera.infrastructure.repositories.sqlite_repository import SQLiteRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_container(**overrides):
    """Create a mock container with sensible defaults for all use cases."""
    container = MagicMock()
    container.deploy_fleet = MagicMock()
    container.deploy_fleet.execute = AsyncMock(return_value=True)
    container.rollback = MagicMock()
    container.rollback.execute = AsyncMock(return_value=True)
    container.execute_local = MagicMock()
    container.execute_local.execute = AsyncMock(
        return_value=SessionId("test-session")
    )
    container.autonomous_loop = MagicMock()
    container.autonomous_loop.execute = AsyncMock(return_value=None)
    container.tmux_adapter = MagicMock()
    container.tmux_adapter.attach_command = AsyncMock(
        return_value="tmux attach -t s"
    )
    container.agent_registry = MagicMock()
    for key, value in overrides.items():
        setattr(container, key, value)
    return container


def _run_cli_subprocess(*args: str, env_extra: dict | None = None):
    """Run the CLI as a subprocess and return CompletedProcess.

    Uses ``python3 -m chimera.presentation.cli.cli`` so that the full
    process lifecycle is exercised (import, parse, execute, exit).
    """
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c",
         "from chimera.presentation.cli.cli import main; main()",
         *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# 1. Help output tests (subprocess - true end-to-end)
# ---------------------------------------------------------------------------

class TestCLIHelpSubprocess:
    """Verify help output via real subprocess invocation."""

    def test_chimera_help_shows_usage(self):
        """chimera --help prints usage information and exits 0."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv = ['chimera', '--help']; "
             "from chimera.presentation.cli.cli import main; main()"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Autonomous Determinism Engine" in result.stdout
        assert "run" in result.stdout
        assert "deploy" in result.stdout

    def test_deploy_help_shows_options(self):
        """chimera deploy --help shows deploy-specific options."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv = ['chimera', 'deploy', '--help']; "
             "from chimera.presentation.cli.cli import main; main()"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--targets" in result.stdout
        assert "--config" in result.stdout
        assert "script_cmd" in result.stdout


# ---------------------------------------------------------------------------
# 2. No-command falls through to help
# ---------------------------------------------------------------------------

class TestCLINoCommand:
    """When no subcommand is given the CLI prints help and exits 0."""

    @pytest.mark.asyncio
    async def test_no_command_prints_help(self, capsys):
        with patch("sys.argv", ["chimera"]):
            await async_main()
        captured = capsys.readouterr()
        assert "Autonomous Determinism Engine" in captured.out


# ---------------------------------------------------------------------------
# 3. chimera run - real temp nix file, mocked adapters
# ---------------------------------------------------------------------------

class TestRunE2E:
    """End-to-end test for the ``run`` subcommand."""

    @pytest.mark.asyncio
    async def test_run_with_temp_nix_file(self, capsys, tmp_path):
        nix_file = tmp_path / "test.nix"
        nix_file.write_text('{ pkgs ? import <nixpkgs> {} }: pkgs.hello')

        container = _make_container()
        container.execute_local.execute = AsyncMock(
            return_value=SessionId("e2e-session")
        )

        with patch("sys.argv", [
            "chimera", "run",
            "-c", str(nix_file),
            "-s", "e2e-session",
            "echo hello",
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Deployment Successful" in captured.out
        assert "e2e-session" in captured.out

        # Verify the use case was called with the right arguments
        container.execute_local.execute.assert_awaited_once_with(
            str(nix_file), "echo hello", "e2e-session"
        )

    @pytest.mark.asyncio
    async def test_run_propagates_file_not_found(self, capsys, tmp_path):
        container = _make_container()
        container.execute_local.execute = AsyncMock(
            side_effect=FileNotFoundError("missing.nix")
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
    async def test_run_propagates_generic_error(self, capsys, tmp_path):
        container = _make_container()
        container.execute_local.execute = AsyncMock(
            side_effect=RuntimeError("nix build failed")
        )

        with patch("sys.argv", [
            "chimera", "run", "-c", "default.nix", "echo hi"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Deployment Failed" in captured.out


# ---------------------------------------------------------------------------
# 4. chimera deploy - mocked container
# ---------------------------------------------------------------------------

class TestDeployE2E:
    """End-to-end test for the ``deploy`` subcommand."""

    @pytest.mark.asyncio
    async def test_deploy_success(self, capsys, tmp_path):
        nix_file = tmp_path / "deploy.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.deploy_fleet.execute = AsyncMock(return_value=True)

        with patch("sys.argv", [
            "chimera", "deploy",
            "-t", "10.0.0.1,10.0.0.2",
            "-c", str(nix_file),
            "-s", "e2e-deploy",
            "nixos-rebuild switch",
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Deploying to fleet" in captured.out
        assert "Deployment Successful" in captured.out

        container.deploy_fleet.execute.assert_awaited_once_with(
            str(nix_file), "nixos-rebuild switch", "e2e-deploy",
            ["10.0.0.1", "10.0.0.2"],
        )

    @pytest.mark.asyncio
    async def test_deploy_failure_exits_nonzero(self, capsys, tmp_path):
        nix_file = tmp_path / "deploy.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.deploy_fleet.execute = AsyncMock(return_value=False)

        with patch("sys.argv", [
            "chimera", "deploy",
            "-t", "10.0.0.1",
            "-c", str(nix_file),
            "echo hi",
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
    async def test_deploy_connection_error(self, capsys, tmp_path):
        nix_file = tmp_path / "deploy.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.deploy_fleet.execute = AsyncMock(
            side_effect=ConnectionError("refused")
        )

        with patch("sys.argv", [
            "chimera", "deploy",
            "-t", "10.0.0.1",
            "-c", str(nix_file),
            "echo hi",
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Connection error" in captured.out


# ---------------------------------------------------------------------------
# 5. chimera rollback - mocked container
# ---------------------------------------------------------------------------

class TestRollbackE2E:
    """End-to-end test for the ``rollback`` subcommand."""

    @pytest.mark.asyncio
    async def test_rollback_success(self, capsys):
        container = _make_container()
        container.rollback.execute = AsyncMock(return_value=True)

        with patch("sys.argv", [
            "chimera", "rollback", "-t", "10.0.0.1,10.0.0.2"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Rollback Successful" in captured.out

        container.rollback.execute.assert_awaited_once_with(
            ["10.0.0.1", "10.0.0.2"], None
        )

    @pytest.mark.asyncio
    async def test_rollback_with_generation(self, capsys):
        container = _make_container()
        container.rollback.execute = AsyncMock(return_value=True)

        with patch("sys.argv", [
            "chimera", "rollback", "-t", "10.0.0.1", "-g", "42"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Rollback Successful" in captured.out
        container.rollback.execute.assert_awaited_once_with(
            ["10.0.0.1"], "42"
        )

    @pytest.mark.asyncio
    async def test_rollback_failure_exits_nonzero(self, capsys):
        container = _make_container()
        container.rollback.execute = AsyncMock(return_value=False)

        with patch("sys.argv", [
            "chimera", "rollback", "-t", "10.0.0.1"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Rollback Failed" in captured.out

    @pytest.mark.asyncio
    async def test_rollback_connection_error(self, capsys):
        container = _make_container()
        container.rollback.execute = AsyncMock(
            side_effect=ConnectionError("timeout")
        )

        with patch("sys.argv", [
            "chimera", "rollback", "-t", "10.0.0.1"
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Connection error" in captured.out


# ---------------------------------------------------------------------------
# 6. chimera watch --once - mocked container
# ---------------------------------------------------------------------------

class TestWatchOnceE2E:
    """End-to-end test for ``chimera watch --once``."""

    @pytest.mark.asyncio
    async def test_watch_once_success(self, capsys, tmp_path):
        nix_file = tmp_path / "watch.nix"
        nix_file.write_text("{}")

        container = _make_container()
        container.autonomous_loop.execute = AsyncMock(return_value=None)

        with patch("sys.argv", [
            "chimera", "watch",
            "-t", "10.0.0.1",
            "-c", str(nix_file),
            "-i", "5",
            "--once",
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                await async_main()

        captured = capsys.readouterr()
        assert "Autonomous Watch" in captured.out

        container.autonomous_loop.execute.assert_awaited_once_with(
            str(nix_file), "chimera-watch", ["10.0.0.1"], 5, True
        )

    @pytest.mark.asyncio
    async def test_watch_once_file_not_found(self, capsys, tmp_path):
        container = _make_container()
        container.autonomous_loop.execute = AsyncMock(
            side_effect=FileNotFoundError("missing.nix")
        )

        with patch("sys.argv", [
            "chimera", "watch",
            "-t", "10.0.0.1",
            "-c", "/nonexistent.nix",
            "--once",
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
    async def test_watch_once_connection_error(self, capsys, tmp_path):
        container = _make_container()
        container.autonomous_loop.execute = AsyncMock(
            side_effect=ConnectionError("unreachable")
        )

        with patch("sys.argv", [
            "chimera", "watch",
            "-t", "10.0.0.1",
            "--once",
        ]):
            with patch(
                "chimera.composition_root.create_container",
                return_value=container,
            ):
                with pytest.raises(SystemExit):
                    await async_main()

        captured = capsys.readouterr()
        assert "Connection error" in captured.out


# ---------------------------------------------------------------------------
# 7. Config file loading integration
# ---------------------------------------------------------------------------

class TestConfigFileIntegration:
    """Verify that a chimera.json config file is loaded correctly."""

    def test_load_config_from_temp_file(self, tmp_path):
        from chimera.infrastructure.config import load_config

        config_data = {
            "nix": {"config_path": "/custom/default.nix"},
            "fleet": {
                "targets": ["192.168.1.1", "192.168.1.2"],
                "session_name": "e2e-fleet",
            },
            "watch": {"interval_seconds": 30},
            "web": {"host": "0.0.0.0", "port": 9090},
            "log_level": "DEBUG",
        }
        config_file = tmp_path / "chimera.json"
        config_file.write_text(json.dumps(config_data))

        config = load_config(path=str(config_file))

        assert config.nix.config_path == "/custom/default.nix"
        assert config.fleet.targets == ("192.168.1.1", "192.168.1.2")
        assert config.fleet.session_name == "e2e-fleet"
        assert config.watch.interval_seconds == 30
        assert config.web.host == "0.0.0.0"
        assert config.web.port == 9090
        assert config.log_level == "DEBUG"

    def test_load_config_with_env_overrides(self, tmp_path):
        from chimera.infrastructure.config import load_config

        config_data = {
            "web": {"host": "127.0.0.1", "port": 8080},
        }
        config_file = tmp_path / "chimera.json"
        config_file.write_text(json.dumps(config_data))

        with patch.dict(os.environ, {
            "CHIMERA_WEB_PORT": "3000",
            "CHIMERA_WEB_HOST": "0.0.0.0",
        }):
            config = load_config(path=str(config_file))

        assert config.web.port == 3000
        assert config.web.host == "0.0.0.0"

    def test_load_config_defaults_when_file_missing(self):
        from chimera.infrastructure.config import load_config

        config = load_config(path="/nonexistent/chimera.json")

        assert config.nix.config_path == "default.nix"
        assert config.fleet.targets == ()
        assert config.web.port == 8080
        assert config.log_level == "WARNING"


# ---------------------------------------------------------------------------
# 8. SQLite repository integration - full lifecycle
# ---------------------------------------------------------------------------

class TestSQLiteRepositoryLifecycle:
    """Full lifecycle test: create DB, record events, query, close,
    reopen, and verify persistence."""

    def test_drift_event_lifecycle(self, tmp_path):
        db_path = str(tmp_path / "test_chimera.db")

        # Phase 1: Create, record, query
        repo = SQLiteRepository(db_path=db_path)
        repo.connect()

        event_id = repo.record_drift(
            node_id="node-1",
            severity="critical",
            expected_hash="abc123",
            actual_hash="def456",
            details="config mismatch",
        )
        assert event_id is not None
        assert event_id > 0

        # Record a second event on a different node
        event_id_2 = repo.record_drift(
            node_id="node-2",
            severity="warning",
            expected_hash="abc123",
            actual_hash="xyz789",
        )
        assert event_id_2 > event_id

        # Query all drift events
        history = repo.get_drift_history()
        assert len(history) == 2

        # Query filtered by node
        node1_history = repo.get_drift_history(node_id="node-1")
        assert len(node1_history) == 1
        assert node1_history[0]["severity"] == "critical"
        assert node1_history[0]["details"] == "config mismatch"

        # Unresolved drifts
        unresolved = repo.get_unresolved_drifts()
        assert len(unresolved) == 2

        # Resolve one
        repo.resolve_drift(event_id, resolution_time_seconds=12.5)
        unresolved = repo.get_unresolved_drifts()
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == event_id_2

        # Stats
        assert repo.get_drift_count() == 2
        assert repo.get_drift_count(node_id="node-1") == 1
        mean_time = repo.get_mean_resolution_time()
        assert mean_time == pytest.approx(12.5)

        repo.close()

        # Phase 2: Reopen and verify persistence
        repo2 = SQLiteRepository(db_path=db_path)
        repo2.connect()

        history2 = repo2.get_drift_history()
        assert len(history2) == 2

        unresolved2 = repo2.get_unresolved_drifts()
        assert len(unresolved2) == 1

        assert repo2.get_drift_count() == 2

        repo2.close()

    def test_playbook_run_lifecycle(self, tmp_path):
        db_path = str(tmp_path / "test_playbook.db")
        repo = SQLiteRepository(db_path=db_path)
        repo.connect()

        run_id = repo.record_playbook_run(
            playbook_id="builtin-rollback",
            playbook_name="rollback",
            node_id="node-1",
            status="running",
            step_results=[{"step": "rollback", "ok": True}],
        )
        assert run_id is not None

        repo.complete_playbook_run(run_id, status="success")

        runs = repo.get_playbook_runs(node_id="node-1")
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
        assert runs[0]["completed_at"] is not None

        repo.close()

        # Reopen and verify
        repo2 = SQLiteRepository(db_path=db_path)
        repo2.connect()
        runs2 = repo2.get_playbook_runs()
        assert len(runs2) == 1
        assert runs2[0]["playbook_name"] == "rollback"
        repo2.close()

    def test_healing_action_lifecycle(self, tmp_path):
        db_path = str(tmp_path / "test_healing.db")
        repo = SQLiteRepository(db_path=db_path)
        repo.connect()

        action_id = repo.record_healing_action(
            node_id="node-1",
            action_type="rollback",
            command="nixos-rebuild switch --rollback",
            success=True,
            duration_seconds=45.2,
            output="Switched to generation 41",
        )
        assert action_id is not None

        repo.record_healing_action(
            node_id="node-1",
            action_type="restart",
            command="systemctl restart chimera-agent",
            success=False,
            duration_seconds=5.0,
            output="Service failed to start",
        )

        history = repo.get_healing_history(node_id="node-1")
        assert len(history) == 2

        all_history = repo.get_healing_history()
        assert len(all_history) == 2

        repo.close()

    def test_slo_violation_lifecycle(self, tmp_path):
        db_path = str(tmp_path / "test_slo.db")
        repo = SQLiteRepository(db_path=db_path)
        repo.connect()

        violation_id = repo.record_slo_violation(
            slo_name="availability",
            target_availability=99.9,
            actual_availability=98.5,
            window_hours=24,
            details="Exceeded error budget",
        )
        assert violation_id is not None

        violations = repo.get_slo_violations()
        assert len(violations) == 1
        assert violations[0]["slo_name"] == "availability"
        assert violations[0]["target_availability"] == 99.9
        assert violations[0]["actual_availability"] == 98.5

        repo.close()

        # Reopen and verify
        repo2 = SQLiteRepository(db_path=db_path)
        repo2.connect()
        assert len(repo2.get_slo_violations()) == 1
        repo2.close()

    def test_empty_database_returns_empty_results(self, tmp_path):
        db_path = str(tmp_path / "test_empty.db")
        repo = SQLiteRepository(db_path=db_path)
        repo.connect()

        assert repo.get_drift_history() == []
        assert repo.get_unresolved_drifts() == []
        assert repo.get_playbook_runs() == []
        assert repo.get_slo_violations() == []
        assert repo.get_healing_history() == []
        assert repo.get_drift_count() == 0
        assert repo.get_mean_resolution_time() is None

        repo.close()
