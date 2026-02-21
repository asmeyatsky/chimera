"""
MCP Clients Package

Architectural Intent:
- Contains MCP client adapters for consuming external services
- Wraps MCP tool calls behind port interfaces
"""

from chimera.infrastructure.mcp_clients.remote_executor_client import (
    MCPClient,
    MCPRemoteExecutorAdapter,
)

__all__ = ["MCPClient", "MCPRemoteExecutorAdapter"]
