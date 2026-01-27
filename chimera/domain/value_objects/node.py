from dataclasses import dataclass

@dataclass(frozen=True)
class Node:
    """
    Value Object representing a remote node in the fleet.
    """
    host: str
    user: str = "root"
    port: int = 22

    def __str__(self):
        return f"{self.user}@{self.host}:{self.port}"
    
    @staticmethod
    def parse(connection_string: str) -> 'Node':
        """
        Parses a string like 'user@host:port' or 'host' into a Node.
        """
        user = "root"
        port = 22
        host = connection_string

        if '@' in host:
            user, host = host.split('@', 1)
        
        if ':' in host:
            host, port_str = host.split(':', 1)
            port = int(port_str)
            
        return Node(host=host, user=user, port=port)
