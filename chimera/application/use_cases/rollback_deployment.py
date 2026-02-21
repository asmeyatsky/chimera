"""
Rollback Deployment Use Case

Architectural Intent:
- Orchestrates rollback of deployments on specified targets
- Delegates to remote executor for actual rollback execution
"""

from typing import List, Optional
from chimera.domain.value_objects.node import Node
from chimera.domain.ports.remote_executor_port import RemoteExecutorPort


class RollbackDeployment:
    def __init__(self, remote_executor: RemoteExecutorPort):
        self.remote_executor = remote_executor

    async def execute(
        self, targets: List[str], generation: Optional[str] = None
    ) -> bool:
        nodes = [Node.parse(t) for t in targets]
        return await self.remote_executor.rollback(nodes, generation)
