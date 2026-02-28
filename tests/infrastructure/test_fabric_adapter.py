"""Tests for FabricAdapter."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash


class TestFabricAdapter:
    def test_get_connection(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1", user="root", port=22)
        with patch("chimera.infrastructure.adapters.fabric_adapter.Connection") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.host = "10.0.0.1"
            mock_conn.user = "root"
            mock_conn_cls.return_value = mock_conn
            conn = adapter._get_connection(node)
            assert conn.host == "10.0.0.1"
            assert conn.user == "root"
            mock_conn_cls.assert_called_once_with(
                host="10.0.0.1",
                user="root",
                port=22,
                connect_timeout=30,
                connect_kwargs={"allow_agent": True, "look_for_keys": True},
            )

    @pytest.mark.asyncio
    async def test_sync_closure_success(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.sync_closure([node], "/nix/store/abc")
            assert result is True

    @pytest.mark.asyncio
    async def test_sync_closure_not_found(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await adapter.sync_closure([node], "/nix/store/abc")
            assert result is True  # graceful fallback

    @pytest.mark.asyncio
    async def test_sync_closure_failure(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.sync_closure([node], "/nix/store/abc")
            assert result is False

    @pytest.mark.asyncio
    async def test_exec_command_empty_nodes(self):
        adapter = FabricAdapter()
        result = await adapter.exec_command([], "echo hi")
        assert result is True

    @pytest.mark.asyncio
    async def test_exec_command_success(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await adapter.exec_command([node], "echo hi")
            assert result is True

    @pytest.mark.asyncio
    async def test_exec_command_failure(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        mock_conn = MagicMock()
        mock_conn.host = "10.0.0.1"
        mock_result = MagicMock()
        mock_result.failed = True
        mock_result.stderr = "command failed"
        mock_group = MagicMock()
        mock_group.run.return_value = {mock_conn: mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await adapter.exec_command([node], "echo hi")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_current_hash_success(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.stdout = "00000000000000000000000000000000"

        mock_conn = MagicMock()
        mock_conn.run.return_value = mock_result

        with patch.object(adapter, "_get_connection", return_value=mock_conn):
            h = await adapter.get_current_hash(node)
            assert isinstance(h, NixHash)

    @pytest.mark.asyncio
    async def test_get_current_hash_failure(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        mock_conn = MagicMock()
        mock_conn.run.side_effect = Exception("connection failed")

        with patch.object(adapter, "_get_connection", return_value=mock_conn):
            h = await adapter.get_current_hash(node)
            assert h is None

    @pytest.mark.asyncio
    async def test_rollback_empty_nodes(self):
        adapter = FabricAdapter()
        result = await adapter.rollback([])
        assert result is True

    @pytest.mark.asyncio
    async def test_rollback_success(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await adapter.rollback([node])
            assert result is True

    @pytest.mark.asyncio
    async def test_rollback_with_generation(self):
        adapter = FabricAdapter()
        node = Node(host="10.0.0.1")

        mock_result = MagicMock()
        mock_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): mock_result}

        with patch("fabric.ThreadingGroup", return_value=mock_group):
            result = await adapter.rollback([node], generation="42")
            assert result is True
            # Verify the command includes the generation
            call_args = mock_group.run.call_args
            assert "42" in call_args[0][0]
