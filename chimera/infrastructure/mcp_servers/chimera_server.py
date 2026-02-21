"""
MCP Server Infrastructure

Architectural Intent:
- MCP server exposing Chimera deployment domain capabilities
- Tools = write operations (commands)
- Resources = read operations (queries)
- Each bounded context has exactly one MCP server

MCP Integration:
- Exposed as 'chimera-service' MCP server
- Tools: execute_deployment, rollback_deployment, check_congruence
- Resources: deployment://{session_id}, node://list
"""

from typing import Any, Callable, Awaitable, Optional
from dataclasses import dataclass


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class MCPResource:
    uri: str
    description: str
    handler: Callable[..., Awaitable[str]]


class MCPServer:
    """
    MCP server exposing Chimera deployment capabilities.

    Each bounded context should have exactly one MCP server.
    Tools = write operations, Resources = read operations.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}

    def tool(
        self,
        name: str,
        description: str = "",
        input_schema: Optional[dict[str, Any]] = None,
    ) -> Callable[[Callable[..., Awaitable[dict[str, Any]]]], MCPTool]:
        def decorator(handler: Callable[..., Awaitable[dict[str, Any]]]) -> MCPTool:
            tool = MCPTool(
                name=name,
                description=description,
                input_schema=input_schema or {},
                handler=handler,
            )
            self._tools[name] = tool
            return tool

        return decorator

    def resource(
        self, uri: str, description: str = ""
    ) -> Callable[[Callable[..., Awaitable[str]]], MCPResource]:
        def decorator(handler: Callable[..., Awaitable[str]]) -> MCPResource:
            resource = MCPResource(
                uri=uri,
                description=description,
                handler=handler,
            )
            self._resources[uri] = resource
            return resource

        return decorator

    async def list_tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    async def list_resources(self) -> list[MCPResource]:
        return list(self._resources.values())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return await self._tools[name].handler(**arguments)

    async def read_resource(self, uri: str) -> str:
        if uri not in self._resources:
            raise ValueError(f"Resource '{uri}' not found")
        return await self._resources[uri].handler()


def create_chimera_server(
    execute_deployment_use_case: Any = None,
    rollback_deployment_use_case: Any = None,
    query_service: Any = None,
) -> MCPServer:
    """
    Factory function to create Chimera MCP server.

    In production, this would be called with actual use case dependencies.
    """
    server = MCPServer("chimera-service")

    if execute_deployment_use_case:

        @server.tool(
            name="execute_deployment",
            description="Execute a deployment to a local or remote target",
            input_schema={
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Path to Nix config",
                    },
                    "command": {"type": "string", "description": "Command to run"},
                    "session_name": {
                        "type": "string",
                        "description": "Tmux session name",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Target nodes",
                    },
                },
                "required": ["config_path", "command"],
            },
        )
        async def execute_deployment(
            config_path: str,
            command: str,
            session_name: str = "chimera",
            targets: list[str] = None,
        ) -> dict[str, Any]:
            return {"status": "success", "message": "Deployment executed"}

    if rollback_deployment_use_case:

        @server.tool(
            name="rollback_deployment",
            description="Rollback deployment to previous generation",
            input_schema={
                "type": "object",
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Target nodes",
                    },
                    "generation": {
                        "type": "string",
                        "description": "Specific generation to rollback to",
                    },
                },
                "required": ["targets"],
            },
        )
        async def rollback_deployment(
            targets: list[str], generation: Optional[str] = None
        ) -> dict[str, Any]:
            return {"status": "success", "message": "Rollback executed"}

    if query_service:

        @server.resource(
            uri="deployment://{session_id}",
            description="Get deployment status by session ID",
        )
        async def get_deployment(session_id: str) -> str:
            return '{"status": "unknown"}'

    return server
