"""
Node Value Object

Architectural Intent:
- Immutable value object representing a remote node in the fleet
- Validates hostname format (DNS, IPv4, IPv6), port bounds, non-empty user
- Supports IPv6 bracket notation in parse() (e.g., user@[::1]:22)
"""

import re
from dataclasses import dataclass

# RFC 1123 hostname: labels of alnum/hyphens, dot-separated
_HOSTNAME_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$"
)

# Simple IPv4 pattern
_IPV4_RE = re.compile(
    r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
)

# IPv6 pattern (simplified — accepts common forms including ::1, fe80::1, etc.)
_IPV6_RE = re.compile(r"^[0-9a-fA-F:]+$")


def _is_valid_hostname(host: str) -> bool:
    """Validate hostname as DNS name, IPv4, or IPv6."""
    if not host:
        return False

    # IPv4
    m = _IPV4_RE.match(host)
    if m:
        return all(0 <= int(g) <= 255 for g in m.groups())

    # IPv6
    if _IPV6_RE.match(host) and ":" in host:
        return True

    # DNS hostname
    if _HOSTNAME_RE.match(host) and len(host) <= 253:
        return True

    return False


@dataclass(frozen=True)
class Node:
    """
    Value Object representing a remote node in the fleet.
    """
    host: str
    user: str = "root"
    port: int = 22

    def __post_init__(self) -> None:
        if not self.user:
            raise ValueError("Node user cannot be empty")
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be 1-65535, got {self.port}")
        if not _is_valid_hostname(self.host):
            raise ValueError(f"Invalid hostname: {self.host!r}")

    def __str__(self) -> str:
        return f"{self.user}@{self.host}:{self.port}"

    @staticmethod
    def parse(connection_string: str) -> "Node":
        """
        Parses a string like 'user@host:port', 'host', or 'user@[::1]:port' into a Node.
        Supports IPv6 bracket notation.
        """
        user = "root"
        port = 22
        host = connection_string.strip()

        if "@" in host:
            user, host = host.split("@", 1)

        # IPv6 bracket notation: [::1]:port or [::1]
        if host.startswith("["):
            bracket_end = host.find("]")
            if bracket_end == -1:
                raise ValueError(f"Unterminated IPv6 bracket in: {connection_string}")
            ipv6_addr = host[1:bracket_end]
            remainder = host[bracket_end + 1:]
            if remainder.startswith(":"):
                port = int(remainder[1:])
            host = ipv6_addr
        elif ":" in host:
            # For non-IPv6, split on last colon for port
            last_colon = host.rfind(":")
            try:
                port = int(host[last_colon + 1:])
                host = host[:last_colon]
            except ValueError:
                pass

        return Node(host=host, user=user, port=port)
