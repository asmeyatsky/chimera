"""
Event Bus Port

Architectural Intent:
- Abstract interface for publishing domain events
- Allows decoupling of event producers from consumers
- Implementation can be in-memory, message queue, or MCP-based
"""

from typing import Protocol, Callable, Awaitable
from chimera.domain.entities.deployment import DomainEvent


class EventBusPort(Protocol):
    async def publish(self, events: list[DomainEvent]) -> None: ...

    def subscribe(
        self, event_type: type, handler: Callable[[DomainEvent], Awaitable[None]]
    ) -> None: ...
