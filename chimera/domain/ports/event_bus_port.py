"""
Event Bus Port

Architectural Intent:
- Abstract interface for publishing domain events
- Allows decoupling of event producers from consumers
- Implementation can be in-memory, message queue, or MCP-based
"""

from typing import Protocol, Callable, Awaitable, runtime_checkable
from chimera.domain.events.event_base import DomainEvent


@runtime_checkable
class EventBusPort(Protocol):
    async def publish(self, events: list[DomainEvent]) -> None: ...

    def subscribe(
        self, event_type: type, handler: Callable[[DomainEvent], Awaitable[None]]
    ) -> None: ...
