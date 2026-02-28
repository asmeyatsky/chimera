"""
ServiceNow ITSM Adapter

Architectural Intent:
- Implements ITSMPort for ServiceNow incident management
- Stub implementation that logs calls for development and testing
- Uses stdlib urllib for the HTTP layer (no external dependencies)

Design Decisions:
- Generates deterministic stub ticket IDs for testability
- Maintains an in-memory incident store for stub mode
- Ready for real ServiceNow REST API integration via urllib.request
"""

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class ServiceNowAdapter:
    """ServiceNow ITSM adapter (stub)."""

    def __init__(
        self,
        instance_url: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        self._instance_url = instance_url
        self._username = username
        self._password = password
        self._incidents: dict[str, dict] = {}

    async def create_incident(
        self, title: str, description: str, severity: str, node_id: str
    ) -> str:
        ticket_id = f"SNW-{uuid.uuid4().hex[:8].upper()}"
        self._incidents[ticket_id] = {
            "ticket_id": ticket_id,
            "title": title,
            "description": description,
            "severity": severity,
            "node_id": node_id,
            "status": "open",
            "resolution": None,
        }
        logger.info(
            "ServiceNow create_incident (stub): %s - %s [severity=%s, node=%s]",
            ticket_id,
            title,
            severity,
            node_id,
        )
        return ticket_id

    async def update_incident(
        self, ticket_id: str, status: str, comment: str
    ) -> None:
        logger.info(
            "ServiceNow update_incident (stub): %s -> %s (%s)",
            ticket_id,
            status,
            comment,
        )
        if ticket_id in self._incidents:
            self._incidents[ticket_id]["status"] = status

    async def resolve_incident(self, ticket_id: str, resolution: str) -> None:
        logger.info(
            "ServiceNow resolve_incident (stub): %s - %s",
            ticket_id,
            resolution,
        )
        if ticket_id in self._incidents:
            self._incidents[ticket_id]["status"] = "resolved"
            self._incidents[ticket_id]["resolution"] = resolution

    async def get_incident(self, ticket_id: str) -> Optional[dict]:
        logger.info("ServiceNow get_incident (stub): %s", ticket_id)
        return self._incidents.get(ticket_id)
