"""
Event Bus Infrastructure

Architectural Intent:
- In-memory event bus implementation for publishing domain events
- Supports async subscription handlers
- Can be extended to use message queues or MCP-based event bus
"""

import logging
from typing import Callable, Awaitable
from chimera.domain.events.event_base import DomainEvent

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable[[DomainEvent], Awaitable[None]]]] = {}

    async def publish(self, events: list[DomainEvent]) -> None:
        for event in events:
            event_type = type(event)
            if event_type in self._handlers:
                for handler in self._handlers[event_type]:
                    await handler(event)

    def subscribe(
        self, event_type: type, handler: Callable[[DomainEvent], Awaitable[None]]
    ) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
