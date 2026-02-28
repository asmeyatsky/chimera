"""Tests for AgentRegistry and orchestrator clients."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC, timedelta

from chimera.infrastructure.agent.chimera_agent import (
    NodeHealth,
    DriftReport,
    AgentStatus,
    DriftSeverity,
)
from chimera.infrastructure.agent.agent_registry import (
    AgentRegistry,
    AgentRecord,
    STALE_THRESHOLD,
)
from chimera.infrastructure.agent.orchestrator_client import (
    InProcessOrchestratorClient,
    MCPOrchestratorClient,
)


class TestAgentRegistry:
    def test_register_new_agent(self):
        registry = AgentRegistry()
        record = registry.register("node-1")
        assert record.node_id == "node-1"
        assert registry.total_count == 1

    def test_register_idempotent(self):
        registry = AgentRegistry()
        r1 = registry.register("node-1")
        r2 = registry.register("node-1")
        assert r1 is r2
        assert registry.total_count == 1

    def test_update_health(self):
        registry = AgentRegistry()
        health = NodeHealth(node_id="node-1", status=AgentStatus.HEALTHY)
        registry.update_health(health)

        record = registry.get("node-1")
        assert record is not None
        assert record.health == health

    def test_update_drift(self):
        registry = AgentRegistry()
        report = DriftReport(
            node_id="node-1",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
        )
        registry.update_drift(report)

        record = registry.get("node-1")
        assert record is not None
        assert record.drift_report == report

    def test_healing_command_lifecycle(self):
        registry = AgentRegistry()
        registry.register("node-1")

        # No command initially
        assert registry.pop_healing_command("node-1") is None

        # Set command
        registry.set_healing_command("node-1", "nix-env --rollback")
        assert registry.pop_healing_command("node-1") == "nix-env --rollback"

        # Consumed after pop
        assert registry.pop_healing_command("node-1") is None

    def test_acknowledge_healing_success(self):
        registry = AgentRegistry()
        report = DriftReport(
            node_id="node-1",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
        )
        registry.update_drift(report)
        assert registry.get("node-1").drift_report is not None

        registry.acknowledge_healing("node-1", success=True)
        assert registry.get("node-1").drift_report is None

    def test_acknowledge_healing_failure_keeps_drift(self):
        registry = AgentRegistry()
        report = DriftReport(
            node_id="node-1",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
        )
        registry.update_drift(report)
        registry.acknowledge_healing("node-1", success=False)
        assert registry.get("node-1").drift_report is not None

    def test_get_healthy(self):
        registry = AgentRegistry()
        registry.update_health(
            NodeHealth(node_id="node-1", status=AgentStatus.HEALTHY)
        )
        registry.update_health(
            NodeHealth(node_id="node-2", status=AgentStatus.DRIFT_DETECTED)
        )

        healthy = registry.get_healthy()
        assert len(healthy) == 1
        assert healthy[0].node_id == "node-1"

    def test_get_drifted(self):
        registry = AgentRegistry()
        registry.update_health(
            NodeHealth(node_id="node-1", status=AgentStatus.HEALTHY)
        )
        registry.update_health(
            NodeHealth(node_id="node-2", status=AgentStatus.DRIFT_DETECTED)
        )

        drifted = registry.get_drifted()
        assert len(drifted) == 1
        assert drifted[0].node_id == "node-2"

    def test_stale_detection(self):
        registry = AgentRegistry()
        record = registry.register("node-1")
        record.last_seen = datetime.now(UTC) - STALE_THRESHOLD - timedelta(seconds=1)

        stale = registry.get_stale()
        assert len(stale) == 1

    def test_remove_agent(self):
        registry = AgentRegistry()
        registry.register("node-1")
        assert registry.total_count == 1
        registry.remove("node-1")
        assert registry.total_count == 0

    def test_counts(self):
        registry = AgentRegistry()
        registry.update_health(
            NodeHealth(node_id="n1", status=AgentStatus.HEALTHY)
        )
        registry.update_health(
            NodeHealth(node_id="n2", status=AgentStatus.DRIFT_DETECTED)
        )
        registry.update_health(
            NodeHealth(node_id="n3", status=AgentStatus.HEALTHY)
        )

        assert registry.total_count == 3
        assert registry.healthy_count == 2
        assert registry.drifted_count == 1


class TestInProcessOrchestratorClient:
    @pytest.mark.asyncio
    async def test_report_health(self):
        registry = AgentRegistry()
        client = InProcessOrchestratorClient(registry)
        health = NodeHealth(node_id="node-1", status=AgentStatus.HEALTHY)

        await client.report_health(health)

        record = registry.get("node-1")
        assert record.health == health

    @pytest.mark.asyncio
    async def test_report_drift(self):
        registry = AgentRegistry()
        client = InProcessOrchestratorClient(registry)
        report = DriftReport(
            node_id="node-1",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
        )

        await client.report_drift(report)

        record = registry.get("node-1")
        assert record.drift_report == report

    @pytest.mark.asyncio
    async def test_fetch_healing_command(self):
        registry = AgentRegistry()
        client = InProcessOrchestratorClient(registry)

        registry.register("node-1")
        registry.set_healing_command("node-1", "nix-env --rollback")

        cmd = await client.fetch_healing_command("node-1")
        assert cmd == "nix-env --rollback"

        # Consumed
        cmd2 = await client.fetch_healing_command("node-1")
        assert cmd2 is None

    @pytest.mark.asyncio
    async def test_acknowledge_healing(self):
        registry = AgentRegistry()
        client = InProcessOrchestratorClient(registry)

        registry.update_drift(
            DriftReport(
                node_id="node-1",
                expected_hash="a",
                actual_hash="b",
                severity=DriftSeverity.HIGH,
            )
        )

        await client.acknowledge_healing("node-1", success=True)
        assert registry.get("node-1").drift_report is None


class TestMCPOrchestratorClient:
    @pytest.mark.asyncio
    async def test_report_health(self):
        mock_mcp = AsyncMock()
        mock_mcp.call_tool = AsyncMock(return_value={"status": "success"})

        client = MCPOrchestratorClient(mock_mcp)
        health = NodeHealth(node_id="node-1", status=AgentStatus.HEALTHY)

        await client.report_health(health)

        mock_mcp.call_tool.assert_called_once()
        call_args = mock_mcp.call_tool.call_args
        assert call_args[0][0] == "report_health"
        assert call_args[1]["arguments"]["node_id"] == "node-1"

    @pytest.mark.asyncio
    async def test_report_drift(self):
        mock_mcp = AsyncMock()
        mock_mcp.call_tool = AsyncMock(return_value={"status": "success"})

        client = MCPOrchestratorClient(mock_mcp)
        report = DriftReport(
            node_id="node-1",
            expected_hash="aaa",
            actual_hash="bbb",
            severity=DriftSeverity.HIGH,
        )

        await client.report_drift(report)

        call_args = mock_mcp.call_tool.call_args
        assert call_args[1]["arguments"]["severity"] == "HIGH"

    @pytest.mark.asyncio
    async def test_fetch_healing_command(self):
        mock_mcp = AsyncMock()
        mock_mcp.call_tool = AsyncMock(
            return_value={"command": "nix-env --rollback"}
        )

        client = MCPOrchestratorClient(mock_mcp)
        cmd = await client.fetch_healing_command("node-1")
        assert cmd == "nix-env --rollback"

    @pytest.mark.asyncio
    async def test_fetch_healing_no_command(self):
        mock_mcp = AsyncMock()
        mock_mcp.call_tool = AsyncMock(return_value={})

        client = MCPOrchestratorClient(mock_mcp)
        cmd = await client.fetch_healing_command("node-1")
        assert cmd is None

    @pytest.mark.asyncio
    async def test_acknowledge_healing(self):
        mock_mcp = AsyncMock()
        mock_mcp.call_tool = AsyncMock(return_value={"status": "success"})

        client = MCPOrchestratorClient(mock_mcp)
        await client.acknowledge_healing("node-1", success=True)

        call_args = mock_mcp.call_tool.call_args
        assert call_args[1]["arguments"]["success"] is True
