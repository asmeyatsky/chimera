"""Tests for MCP stdio JSON-RPC transport."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from chimera.infrastructure.mcp_servers.chimera_server import (
    MCPServer,
    MCPError,
)
from chimera.infrastructure.mcp_servers.stdio_transport import (
    _encode_message,
    _parse_header,
    _read_message,
    _dispatch,
    run_stdio,
    JSONRPC_VERSION,
    MCP_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    INTERNAL_ERROR,
)


def _make_request(method: str, params: dict = None, id: int = 1) -> bytes:
    """Helper: build a Content-Length-framed JSON-RPC request."""
    msg = {"jsonrpc": JSONRPC_VERSION, "method": method, "id": id}
    if params is not None:
        msg["params"] = params
    return _encode_message(msg)


def _make_notification(method: str, params: dict = None) -> bytes:
    """Helper: build a Content-Length-framed JSON-RPC notification (no id)."""
    msg = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        msg["params"] = params
    return _encode_message(msg)


def _make_server_with_tools() -> MCPServer:
    """Create an MCPServer with a sample tool and resource."""
    server = MCPServer("test-server")

    @server.tool(
        name="echo",
        description="Echo back the input",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    )
    async def echo(message: str) -> dict:
        return {"echoed": message}

    @server.tool(
        name="failing_tool",
        description="A tool that always fails",
        input_schema={"type": "object", "properties": {}},
    )
    async def failing_tool() -> dict:
        raise ValueError("intentional failure")

    @server.resource(uri="test://status", description="Test status resource")
    async def test_status() -> str:
        return json.dumps({"status": "ok"})

    return server


class TestMessageParsing:
    """Test Content-Length framed message parsing."""

    def test_encode_message(self):
        msg = {"jsonrpc": "2.0", "id": 1, "result": {}}
        encoded = _encode_message(msg)
        body = json.dumps(msg).encode("utf-8")
        expected_header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        assert encoded == expected_header + body

    def test_parse_header_valid(self):
        header = b"Content-Length: 42\r\n\r\n"
        assert _parse_header(header) == 42

    def test_parse_header_missing(self):
        with pytest.raises(ValueError, match="Missing Content-Length"):
            _parse_header(b"X-Other: foo\r\n\r\n")

    @pytest.mark.asyncio
    async def test_read_message_parses_body(self):
        msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
        data = _encode_message(msg)
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()
        result = await _read_message(reader)
        assert result == msg

    @pytest.mark.asyncio
    async def test_read_message_eof(self):
        reader = asyncio.StreamReader()
        reader.feed_eof()
        result = await _read_message(reader)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_multiple_messages(self):
        msg1 = {"jsonrpc": "2.0", "method": "a", "id": 1}
        msg2 = {"jsonrpc": "2.0", "method": "b", "id": 2}
        data = _encode_message(msg1) + _encode_message(msg2)
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()
        r1 = await _read_message(reader)
        r2 = await _read_message(reader)
        assert r1 == msg1
        assert r2 == msg2


class TestInitializeHandshake:
    """Test the initialize/initialized handshake."""

    @pytest.mark.asyncio
    async def test_initialize_response(self):
        server = MCPServer("test-server")
        msg = {"jsonrpc": JSONRPC_VERSION, "method": "initialize", "id": 1, "params": {}}
        response = await _dispatch(server, msg)
        assert response["id"] == 1
        result = response["result"]
        assert result["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert "tools" in result["capabilities"]
        assert "resources" in result["capabilities"]
        assert result["serverInfo"]["name"] == "test-server"

    @pytest.mark.asyncio
    async def test_initialized_notification_no_response(self):
        server = MCPServer("test-server")
        msg = {"jsonrpc": JSONRPC_VERSION, "method": "notifications/initialized"}
        response = await _dispatch(server, msg)
        assert response is None


class TestToolsList:
    """Test tools/list response."""

    @pytest.mark.asyncio
    async def test_tools_list_empty(self):
        server = MCPServer("test-server")
        msg = {"jsonrpc": JSONRPC_VERSION, "method": "tools/list", "id": 1, "params": {}}
        response = await _dispatch(server, msg)
        assert response["result"]["tools"] == []

    @pytest.mark.asyncio
    async def test_tools_list_with_tools(self):
        server = _make_server_with_tools()
        msg = {"jsonrpc": JSONRPC_VERSION, "method": "tools/list", "id": 1, "params": {}}
        response = await _dispatch(server, msg)
        tools = response["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "echo" in names
        assert "failing_tool" in names
        # Check schema is included
        echo_tool = next(t for t in tools if t["name"] == "echo")
        assert echo_tool["inputSchema"]["type"] == "object"
        assert "description" in echo_tool


class TestToolsCall:
    """Test tools/call routing."""

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        server = _make_server_with_tools()
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "tools/call",
            "id": 1,
            "params": {"name": "echo", "arguments": {"message": "hello"}},
        }
        response = await _dispatch(server, msg)
        assert "error" not in response
        content = response["result"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        parsed = json.loads(content[0]["text"])
        assert parsed["echoed"] == "hello"

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        server = MCPServer("test-server")
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "tools/call",
            "id": 1,
            "params": {"name": "nonexistent", "arguments": {}},
        }
        response = await _dispatch(server, msg)
        assert "error" in response
        assert response["error"]["code"] == INTERNAL_ERROR

    @pytest.mark.asyncio
    async def test_call_tool_handler_error(self):
        server = _make_server_with_tools()
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "tools/call",
            "id": 1,
            "params": {"name": "failing_tool", "arguments": {}},
        }
        response = await _dispatch(server, msg)
        assert "error" in response
        assert response["error"]["code"] == INTERNAL_ERROR


class TestResourcesList:
    """Test resources/list response."""

    @pytest.mark.asyncio
    async def test_resources_list_empty(self):
        server = MCPServer("test-server")
        msg = {"jsonrpc": JSONRPC_VERSION, "method": "resources/list", "id": 1, "params": {}}
        response = await _dispatch(server, msg)
        assert response["result"]["resources"] == []

    @pytest.mark.asyncio
    async def test_resources_list_with_resources(self):
        server = _make_server_with_tools()
        msg = {"jsonrpc": JSONRPC_VERSION, "method": "resources/list", "id": 1, "params": {}}
        response = await _dispatch(server, msg)
        resources = response["result"]["resources"]
        assert len(resources) == 1
        assert resources[0]["uri"] == "test://status"
        assert resources[0]["mimeType"] == "application/json"


class TestResourcesRead:
    """Test resources/read routing."""

    @pytest.mark.asyncio
    async def test_read_resource_success(self):
        server = _make_server_with_tools()
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "resources/read",
            "id": 1,
            "params": {"uri": "test://status"},
        }
        response = await _dispatch(server, msg)
        assert "error" not in response
        contents = response["result"]["contents"]
        assert len(contents) == 1
        assert contents[0]["uri"] == "test://status"
        parsed = json.loads(contents[0]["text"])
        assert parsed["status"] == "ok"

    @pytest.mark.asyncio
    async def test_read_resource_not_found(self):
        server = MCPServer("test-server")
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "resources/read",
            "id": 1,
            "params": {"uri": "unknown://foo"},
        }
        response = await _dispatch(server, msg)
        assert "error" in response
        assert response["error"]["code"] == INTERNAL_ERROR


class TestUnknownMethod:
    """Test unknown method returns error."""

    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self):
        server = MCPServer("test-server")
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "nonexistent/method",
            "id": 1,
            "params": {},
        }
        response = await _dispatch(server, msg)
        assert "error" in response
        assert response["error"]["code"] == METHOD_NOT_FOUND
        assert "nonexistent/method" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_unknown_notification_ignored(self):
        server = MCPServer("test-server")
        msg = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "nonexistent/notification",
        }
        response = await _dispatch(server, msg)
        assert response is None


class TestRunStdio:
    """Integration test for the full stdio transport loop."""

    @pytest.mark.asyncio
    async def test_full_session(self):
        """Test a complete MCP session: initialize -> tools/list -> shutdown."""
        server = _make_server_with_tools()

        # Build input stream: initialize, initialized notification, tools/list, shutdown
        input_data = (
            _make_request("initialize", {}, id=1)
            + _make_notification("notifications/initialized")
            + _make_request("tools/list", {}, id=2)
            + _make_request("shutdown", {}, id=3)
        )

        reader = asyncio.StreamReader()
        reader.feed_data(input_data)
        reader.feed_eof()

        # Capture output
        collected = bytearray()

        class FakeWriter:
            def write(self, data: bytes):
                collected.extend(data)

            async def drain(self):
                pass

        writer = FakeWriter()
        await run_stdio(server, reader=reader, writer=writer)

        # Parse responses from collected output
        out_reader = asyncio.StreamReader()
        out_reader.feed_data(bytes(collected))
        out_reader.feed_eof()

        responses = []
        while True:
            msg = await _read_message(out_reader)
            if msg is None:
                break
            responses.append(msg)

        # Should have 3 responses: initialize, tools/list, shutdown
        assert len(responses) == 3

        # 1) initialize response
        assert responses[0]["id"] == 1
        assert "protocolVersion" in responses[0]["result"]

        # 2) tools/list response
        assert responses[1]["id"] == 2
        tool_names = [t["name"] for t in responses[1]["result"]["tools"]]
        assert "echo" in tool_names

        # 3) shutdown response
        assert responses[2]["id"] == 3
        assert responses[2]["result"] == {}

    @pytest.mark.asyncio
    async def test_eof_terminates(self):
        """Transport exits cleanly on EOF."""
        server = MCPServer("test-server")

        reader = asyncio.StreamReader()
        reader.feed_eof()

        collected = bytearray()

        class FakeWriter:
            def write(self, data: bytes):
                collected.extend(data)

            async def drain(self):
                pass

        writer = FakeWriter()
        await run_stdio(server, reader=reader, writer=writer)
        # No responses expected
        assert len(collected) == 0
