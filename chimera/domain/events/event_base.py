"""
Domain Events Module

Architectural Intent:
- Base class for domain events following DDD principles
- Events are immutable and capture significant domain occurrences
- Events are collected in aggregates and dispatched via event bus
- This is the canonical source of DomainEvent for the entire codebase
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    aggregate_id: str = ""
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at,
            "event_type": self.event_type,
        }
