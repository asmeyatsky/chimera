"""
ITSM Port (IT Service Management)

Architectural Intent:
- Port interface for incident management integration (ServiceNow, Jira, etc.)
- Abstracts ticket lifecycle: create, update, resolve, query
- Enables automated incident creation from drift detection and SLO breaches

Design Decisions:
- Uses Protocol for structural typing (no inheritance needed)
- Methods cover the core incident lifecycle
- Returns ticket IDs as strings to remain provider-agnostic
"""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ITSMPort(Protocol):
    """Port for IT Service Management operations."""

    async def create_incident(
        self, title: str, description: str, severity: str, node_id: str
    ) -> str:
        """Create an incident ticket. Returns ticket ID."""
        ...

    async def update_incident(
        self, ticket_id: str, status: str, comment: str
    ) -> None:
        """Update an existing incident."""
        ...

    async def resolve_incident(self, ticket_id: str, resolution: str) -> None:
        """Resolve/close an incident."""
        ...

    async def get_incident(self, ticket_id: str) -> Optional[dict]:
        """Get incident details."""
        ...
