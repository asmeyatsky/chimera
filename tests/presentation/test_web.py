"""Tests for the Chimera web dashboard.

Uses mocks for AgentRegistry and RollbackDeployment so the tests run without
any real infrastructure or network dependencies.
"""

import asyncio
import json
import urllib.request
import urllib.error

import pytest
import pytest_asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from chimera.infrastructure.agent.agent_registry import AgentRegistry, AgentRecord
from chimera.infrastructure.agent.chimera_agent import NodeHealth, AgentStatus
from chimera.application.use_cases.rollback_deployment import RollbackDeployment
from chimera.presentation.web.app import ChimeraWebApp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_health(node_id: str, status: AgentStatus = AgentStatus.HEALTHY) -> NodeHealth:
    """Create a minimal NodeHealth instance."""
    return NodeHealth(node_id=node_id, status=status)


def _make_record(node_id: str, status: AgentStatus = AgentStatus.HEALTHY) -> AgentRecord:
    """Create an AgentRecord with health populated."""
    return AgentRecord(
        node_id=node_id,
        health=_make_health(node_id, status),
        last_seen=datetime.now(UTC),
    )


@pytest.fixture()
def registry() -> AgentRegistry:
    """Return a real AgentRegistry pre-populated with test data."""
    reg = AgentRegistry()
    reg.update_health(_make_health("node-1", AgentStatus.HEALTHY))
    reg.update_health(_make_health("node-2", AgentStatus.DRIFT_DETECTED))
    return reg


@pytest.fixture()
def rollback_uc() -> MagicMock:
    """Return a mock RollbackDeployment use case."""
    mock = MagicMock(spec=RollbackDeployment)
    mock.execute = AsyncMock(return_value=True)
    return mock


@pytest_asyncio.fixture()
async def web_app(registry, rollback_uc):
    """Start a ChimeraWebApp on a random port, yield (app, base_url), then stop."""
    app = ChimeraWebApp(registry=registry, rollback=rollback_uc)
    # Port 0 lets the OS pick a free port
    await app.start("127.0.0.1", 0)
    port = app._server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    yield app, base
    app.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(url: str) -> tuple[int, dict | str]:
    """Send a GET request and return (status_code, parsed_body)."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                return resp.status, json.loads(body)
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def _post(url: str, data: dict) -> tuple[int, dict]:
    """Send a POST request with JSON body and return (status_code, parsed_body)."""
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFleetStatus:
    """GET /api/fleet endpoint."""

    @pytest.mark.asyncio
    async def test_fleet_status_returns_json(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/fleet")

        assert status == 200
        assert isinstance(data, dict)
        assert data["total"] == 2
        assert "nodes" in data
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_fleet_status_counts(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/fleet")

        assert data["healthy"] == 1
        assert data["drifted"] == 1

    @pytest.mark.asyncio
    async def test_fleet_node_fields(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/fleet")

        node_ids = {n["node_id"] for n in data["nodes"]}
        assert "node-1" in node_ids
        assert "node-2" in node_ids

        for node in data["nodes"]:
            assert "status" in node
            assert "last_seen" in node
            assert "is_stale" in node


class TestNodeHealth:
    """GET /api/nodes/{node_id} endpoint."""

    @pytest.mark.asyncio
    async def test_existing_node(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/nodes/node-1")

        assert status == 200
        assert data["node_id"] == "node-1"
        assert data["status"] == "HEALTHY"

    @pytest.mark.asyncio
    async def test_drifted_node(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/nodes/node-2")

        assert status == 200
        assert data["node_id"] == "node-2"
        assert data["status"] == "DRIFT_DETECTED"

    @pytest.mark.asyncio
    async def test_missing_node_returns_404(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/nodes/nonexistent")

        assert status == 404
        assert "error" in data


class TestRollback:
    """POST /api/rollback endpoint."""

    @pytest.mark.asyncio
    async def test_rollback_success(self, web_app, rollback_uc):
        _, base = web_app
        status, data = _post(f"{base}/api/rollback", {
            "targets": ["10.0.0.1"],
        })

        assert status == 200
        assert data["success"] is True
        assert data["targets"] == ["10.0.0.1"]
        rollback_uc.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_with_generation(self, web_app, rollback_uc):
        _, base = web_app
        status, data = _post(f"{base}/api/rollback", {
            "targets": ["10.0.0.1", "10.0.0.2"],
            "generation": "gen-42",
        })

        assert status == 200
        assert data["success"] is True
        rollback_uc.execute.assert_called_once_with(
            targets=["10.0.0.1", "10.0.0.2"],
            generation="gen-42",
        )

    @pytest.mark.asyncio
    async def test_rollback_failure(self, web_app, rollback_uc):
        rollback_uc.execute = AsyncMock(return_value=False)

        _, base = web_app
        status, data = _post(f"{base}/api/rollback", {
            "targets": ["10.0.0.1"],
        })

        assert status == 500
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_rollback_missing_targets(self, web_app):
        _, base = web_app
        status, data = _post(f"{base}/api/rollback", {})

        assert status == 400
        assert "error" in data

    @pytest.mark.asyncio
    async def test_rollback_empty_targets(self, web_app):
        _, base = web_app
        status, data = _post(f"{base}/api/rollback", {"targets": []})

        assert status == 400
        assert "error" in data


class TestDashboard:
    """GET / endpoint."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_html(self, web_app):
        _, base = web_app
        status, body = _get(base + "/")

        assert status == 200
        assert isinstance(body, str)
        assert "Chimera Fleet Dashboard" in body
        assert "<table>" in body


class TestNotFound:
    """Unknown routes return 404."""

    @pytest.mark.asyncio
    async def test_unknown_get_returns_404(self, web_app):
        _, base = web_app
        status, data = _get(f"{base}/api/unknown")

        assert status == 404
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unknown_post_returns_404(self, web_app):
        _, base = web_app
        status, data = _post(f"{base}/api/unknown", {})

        assert status == 404
