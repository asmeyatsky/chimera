"""Tests for MCP server schema compliance."""

import pytest
from unittest.mock import AsyncMock
from chimera.infrastructure.mcp_servers.chimera_server import (
    create_chimera_server,
    MCPServer,
    MCPError,
)


class TestMCPServer:
    @pytest.mark.asyncio
    async def test_list_tools_empty(self):
        server = MCPServer("test")
        tools = await server.list_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        server = MCPServer("test")
        with pytest.raises(MCPError, match="not found"):
            await server.call_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_read_unknown_resource(self):
        server = MCPServer("test")
        with pytest.raises(MCPError, match="not found"):
            await server.read_resource("unknown://")

    @pytest.mark.asyncio
    async def test_tool_registration(self):
        server = MCPServer("test")

        @server.tool(name="my_tool", description="test tool")
        async def my_tool() -> dict:
            return {"result": "ok"}

        tools = await server.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "my_tool"

    @pytest.mark.asyncio
    async def test_resource_registration(self):
        server = MCPServer("test")

        @server.resource(uri="test://data", description="test resource")
        async def my_resource() -> str:
            return '{"data": "ok"}'

        resources = await server.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == "test://data"


class TestChimeraServerFactory:
    @pytest.mark.asyncio
    async def test_creates_with_deploy(self):
        deploy = AsyncMock()
        server = create_chimera_server(deploy_fleet_use_case=deploy)
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "execute_deployment" in tool_names
        assert "check_congruence" in tool_names

    @pytest.mark.asyncio
    async def test_creates_with_rollback(self):
        rollback = AsyncMock()
        server = create_chimera_server(rollback_deployment_use_case=rollback)
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert "rollback_deployment" in tool_names

    @pytest.mark.asyncio
    async def test_node_health_resource(self):
        server = create_chimera_server()
        resources = await server.list_resources()
        uris = [r.uri for r in resources]
        assert "node://health" in uris

    @pytest.mark.asyncio
    async def test_execute_deployment_tool(self):
        deploy = AsyncMock()
        deploy.execute = AsyncMock(return_value=True)
        server = create_chimera_server(deploy_fleet_use_case=deploy)

        result = await server.call_tool(
            "execute_deployment",
            {
                "config_path": "default.nix",
                "command": "echo hi",
                "targets": ["localhost"],
            },
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_schemas_have_required_fields(self):
        deploy = AsyncMock()
        rollback = AsyncMock()
        server = create_chimera_server(deploy, rollback)
        tools = await server.list_tools()

        for tool in tools:
            assert tool.input_schema.get("type") == "object"
            assert "properties" in tool.input_schema
