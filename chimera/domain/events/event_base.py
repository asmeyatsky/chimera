"""
Domain Events Module

Architectural Intent:
- Base classes for domain events following DDD principles
- Events are immutable and capture significant domain occurrences
- Events are collected in aggregates and dispatched via event bus
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    occurred_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(), init=False, repr=False
    )
    aggregate_id: str = ""

    def __post_init__(self):
        pass

    def with_aggregate_id(self, aggregate_id: str) -> "DomainEvent":
        object.__setattr__(self, "aggregate_id", aggregate_id)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at,
            "event_type": self.__class__.__name__,
        }
