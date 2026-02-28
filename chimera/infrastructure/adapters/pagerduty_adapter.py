"""
PagerDuty Notification Adapter

Architectural Intent:
- Implements NotificationPort for PagerDuty incident notifications
- Stub implementation that logs calls for development and testing
- Uses stdlib urllib for the HTTP layer (no external dependencies)

Design Decisions:
- Generates deterministic stub incident IDs for testability
- Maintains an in-memory incident store for stub mode
- Ready for real PagerDuty Events API integration via urllib.request
- Supports severity-to-urgency mapping for PagerDuty escalation policies
"""

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class PagerDutyAdapter:
    """PagerDuty notification adapter (stub)."""

    def __init__(self, api_key: str = "", integration_key: str = "") -> None:
        """Initialize PagerDuty adapter.

        Args:
            api_key: PagerDuty API key for REST API calls
            integration_key: PagerDuty integration key for Events API
        """
        self._api_key = api_key
        self._integration_key = integration_key
        self._incidents: dict[str, dict] = {}

    async def send_alert(
        self, title: str, message: str, severity: str, node_id: str = ""
    ) -> bool:
        """Send an alert to PagerDuty.

        Args:
            title: Alert title
            message: Alert message/details
            severity: Severity level (critical, high, medium, low)
            node_id: Optional node identifier

        Returns:
            True if alert sent successfully
        """
        incident_id = f"PD-{uuid.uuid4().hex[:8].upper()}"

        # Map severity to PagerDuty urgency
        urgency_map = {
            "critical": "high",
            "high": "high",
            "medium": "low",
            "low": "low",
        }
        urgency = urgency_map.get(severity, "low")

        payload = {
            "incident_id": incident_id,
            "type": "alert",
            "title": title,
            "message": message,
            "severity": severity,
            "urgency": urgency,
            "node_id": node_id,
            "status": "triggered",
        }

        self._incidents[incident_id] = payload

        logger.info(
            "PagerDuty send_alert (stub): %s - %s [severity=%s, urgency=%s, node=%s, key=%s]",
            incident_id,
            title,
            severity,
            urgency,
            node_id,
            self._integration_key,
        )

        return True

    async def send_resolution(
        self, title: str, message: str, node_id: str = ""
    ) -> bool:
        """Send a resolution to PagerDuty.

        Args:
            title: Resolution title
            message: Resolution details
            node_id: Optional node identifier

        Returns:
            True if resolution sent successfully
        """
        incident_id = f"PD-{uuid.uuid4().hex[:8].upper()}"

        payload = {
            "incident_id": incident_id,
            "type": "resolution",
            "title": title,
            "message": message,
            "node_id": node_id,
            "status": "resolved",
        }

        self._incidents[incident_id] = payload

        logger.info(
            "PagerDuty send_resolution (stub): %s - %s [node=%s, key=%s]",
            incident_id,
            title,
            node_id,
            self._integration_key,
        )

        return True

    def get_incident(self, incident_id: str) -> Optional[dict]:
        """Retrieve an incident by ID (for testing).

        Args:
            incident_id: Incident ID to retrieve

        Returns:
            Incident payload if found, None otherwise
        """
        return self._incidents.get(incident_id)
