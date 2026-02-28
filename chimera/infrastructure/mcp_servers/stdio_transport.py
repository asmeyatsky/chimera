"""
MCP Stdio Transport

Architectural Intent:
- JSON-RPC over stdin/stdout transport layer for MCP protocol
- Reads Content-Length framed messages from stdin
- Routes MCP methods to MCPServer instance
- Writes Content-Length framed JSON-RPC responses to stdout
- Uses only stdlib (json, sys, asyncio)

MCP Integration:
- Handles initialize/initialized handshake
- Routes tools/list, tools/call, resources/list, resources/read
- Graceful shutdown on notifications/shutdown
"""

import json
import sys
import asyncio
from typing import Any, Optional

from chimera.infrastructure.mcp_servers.chimera_server import MCPServer, MCPError

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _encode_message(obj: dict[str, Any]) -> bytes:
    """Encode a JSON-RPC message with Content-Length header."""
    body = json.dumps(obj).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _parse_header(header_data: bytes) -> int:
    """Parse Content-Length from header bytes. Returns content length."""
    header_str = header_data.decode("ascii")
    for line in header_str.split("\r\n"):
        line = line.strip()
        if line.lower().startswith("content-length:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError("Missing Content-Length header")


async def _read_message(reader: asyncio.StreamReader) -> Optional[dict[str, Any]]:
    """Read a single JSON-RPC message from the stream.

    Reads Content-Length header, then reads that many bytes of JSON body.
    Returns None on EOF.
    """
    # Read headers until we hit the empty line (\r\n\r\n)
    header_bytes = b""
    while True:
        line = await reader.readline()
        if not line:
            return None  # EOF
        header_bytes += line
        if header_bytes.endswith(b"\r\n\r\n"):
            break

    content_length = _parse_header(header_bytes)
    body = await reader.readexactly(content_length)
    return json.loads(body.decode("utf-8"))


def _make_response(id: Any, result: Any) -> dict[str, Any]:
    """Create a JSON-RPC success response."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "result": result,
    }


def _make_error(id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """Create a JSON-RPC error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "error": error,
    }


async def _handle_initialize(
    server: MCPServer, params: dict[str, Any]
) -> dict[str, Any]:
    """Handle the initialize request, returning server capabilities."""
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
        },
        "serverInfo": {
            "name": server.name,
            "version": "1.0.0",
        },
    }


async def _handle_tools_list(
    server: MCPServer, params: dict[str, Any]
) -> dict[str, Any]:
    """Handle tools/list request."""
    tools = await server.list_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in tools
        ]
    }


async def _handle_tools_call(
    server: MCPServer, params: dict[str, Any]
) -> dict[str, Any]:
    """Handle tools/call request."""
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    result = await server.call_tool(name, arguments)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result),
            }
        ]
    }


async def _handle_resources_list(
    server: MCPServer, params: dict[str, Any]
) -> dict[str, Any]:
    """Handle resources/list request."""
    resources = await server.list_resources()
    return {
        "resources": [
            {
                "uri": r.uri,
                "description": r.description,
                "mimeType": "application/json",
            }
            for r in resources
        ]
    }


async def _handle_resources_read(
    server: MCPServer, params: dict[str, Any]
) -> dict[str, Any]:
    """Handle resources/read request."""
    uri = params.get("uri", "")
    content = await server.read_resource(uri)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": content,
            }
        ]
    }


# Method dispatch table
_METHOD_HANDLERS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
    "resources/list": _handle_resources_list,
    "resources/read": _handle_resources_read,
}

# Notifications that should be silently acknowledged (no response)
_NOTIFICATIONS = {"notifications/initialized", "notifications/cancelled"}


async def _dispatch(
    server: MCPServer, message: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Dispatch a JSON-RPC message and return the response, or None for notifications."""
    method = message.get("method", "")
    msg_id = message.get("id")
    params = message.get("params", {})

    # Notifications have no id and require no response
    if msg_id is None:
        # This is a notification
        if method in _NOTIFICATIONS:
            return None
        if method == "shutdown":
            return None
        # Unknown notification, silently ignore
        return None

    # Handle shutdown request (with id)
    if method == "shutdown":
        return _make_response(msg_id, {})

    # Route to handler
    handler = _METHOD_HANDLERS.get(method)
    if handler is None:
        return _make_error(msg_id, METHOD_NOT_FOUND, f"Method not found: {method}")

    try:
        result = await handler(server, params)
        return _make_response(msg_id, result)
    except MCPError as e:
        return _make_error(msg_id, INTERNAL_ERROR, str(e), e.to_dict())
    except Exception as e:
        return _make_error(msg_id, INTERNAL_ERROR, f"Internal error: {e}")


async def run_stdio(
    server: MCPServer,
    reader: Optional[asyncio.StreamReader] = None,
    writer: Optional[asyncio.StreamWriter] = None,
) -> None:
    """Run the MCP server using stdio JSON-RPC transport.

    Args:
        server: The MCPServer instance to serve.
        reader: Optional StreamReader (defaults to stdin).
        writer: Optional StreamWriter (defaults to stdout).
    """
    if reader is None:
        loop = asyncio.get_event_loop()
        _reader = asyncio.StreamReader()
        transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(_reader), sys.stdin.buffer
        )
        reader = _reader

    use_raw_writer = writer is None
    raw_stdout = None
    if use_raw_writer:
        raw_stdout = sys.stdout.buffer

    running = True
    while running:
        try:
            message = await _read_message(reader)
        except (asyncio.IncompleteReadError, ValueError):
            break

        if message is None:
            break  # EOF

        method = message.get("method", "")

        response = await _dispatch(server, message)

        if response is not None:
            data = _encode_message(response)
            if writer is not None:
                writer.write(data)
                await writer.drain()
            elif raw_stdout is not None:
                raw_stdout.write(data)
                raw_stdout.flush()

        # Exit on shutdown
        if method == "shutdown":
            running = False
