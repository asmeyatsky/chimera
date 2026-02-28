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
- Resources: deployment://{session_id}, node://health
"""

from typing import Any, Callable, Awaitable, Optional
from dataclasses import dataclass
import json


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


class MCPError(Exception):
    """Structured MCP error."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "details": self.details,
            }
        }


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
            raise MCPError("tool_not_found", f"Tool '{name}' not found")
        try:
            return await self._tools[name].handler(**arguments)
        except MCPError:
            raise
        except Exception as e:
            raise MCPError("internal_error", str(e))

    async def read_resource(self, uri: str) -> str:
        if uri not in self._resources:
            raise MCPError("resource_not_found", f"Resource '{uri}' not found")
        return await self._resources[uri].handler()


def create_chimera_server(
    deploy_fleet_use_case: Any = None,
    rollback_deployment_use_case: Any = None,
    query_service: Any = None,
) -> MCPServer:
    """
    Factory function to create Chimera MCP server with wired use cases.

    MCP Integration:
    - Exposed as 'chimera-service' MCP server
    - Tools: execute_deployment, rollback_deployment, check_congruence
    - Resources: deployment://{session_id}, node://health
    """
    server = MCPServer("chimera-service")

    if deploy_fleet_use_case:

        @server.tool(
            name="execute_deployment",
            description="Execute a deployment to a local or remote target",
            input_schema={
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Path to Nix config file",
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to run in nix-shell",
                    },
                    "session_name": {
                        "type": "string",
                        "description": "Tmux session name",
                        "default": "chimera",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Target nodes (e.g., ['root@10.0.0.1:22'])",
                    },
                },
                "required": ["config_path", "command"],
            },
        )
        async def execute_deployment(
            config_path: str,
            command: str,
            session_name: str = "chimera",
            targets: Optional[list[str]] = None,
        ) -> dict[str, Any]:
            try:
                target_list = targets if targets else ["localhost"]
                success = await deploy_fleet_use_case.execute(
                    config_path, command, session_name, target_list
                )
                return {
                    "status": "success" if success else "failed",
                    "message": "Deployment completed"
                    if success
                    else "Deployment failed",
                    "targets": target_list,
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @server.tool(
            name="check_congruence",
            description="Check configuration congruence across fleet nodes",
            input_schema={
                "type": "object",
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Target nodes to check",
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Path to expected Nix config",
                    },
                },
                "required": ["targets", "config_path"],
            },
        )
        async def check_congruence(
            targets: list[str],
            config_path: str,
        ) -> dict[str, Any]:
            return {
                "status": "success",
                "message": "Congruence check not yet implemented",
                "targets": targets,
            }

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
                        "description": "Target nodes to rollback",
                    },
                    "generation": {
                        "type": "string",
                        "description": "Specific generation to rollback to (optional)",
                    },
                },
                "required": ["targets"],
            },
        )
        async def rollback_deployment(
            targets: list[str], generation: Optional[str] = None
        ) -> dict[str, Any]:
            try:
                success = await rollback_deployment_use_case.execute(
                    targets, generation
                )
                return {
                    "status": "success" if success else "failed",
                    "message": "Rollback completed" if success else "Rollback failed",
                    "targets": targets,
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

    @server.resource(
        uri="node://health",
        description="Get health status of all known nodes",
    )
    async def get_node_health() -> str:
        return json.dumps({"nodes": [], "message": "No nodes currently tracked"})

    if query_service:

        @server.resource(
            uri="deployment://{session_id}",
            description="Get deployment status by session ID",
        )
        async def get_deployment(session_id: str) -> str:
            return json.dumps({"status": "unknown"})

    return server
