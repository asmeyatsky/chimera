from typing import List, Optional
from chimera.domain.value_objects.node import Node
from chimera.domain.ports.remote_executor_port import RemoteExecutorPort

class RollbackDeployment:
    def __init__(self, remote_executor: RemoteExecutorPort):
        self.remote_executor = remote_executor

    def execute(self, targets: List[str], generation: Optional[str] = None) -> bool:
        """
        Rolls back the deployment on specified targets.
        """
        nodes = [Node.parse(t) for t in targets]
        return self.remote_executor.rollback(nodes, generation)
