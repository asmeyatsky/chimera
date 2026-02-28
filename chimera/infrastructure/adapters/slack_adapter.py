"""
Slack Notification Adapter

Architectural Intent:
- Implements NotificationPort for Slack webhook notifications
- Stub implementation that logs calls for development and testing
- Uses stdlib urllib for the HTTP layer (no external dependencies)

Design Decisions:
- Generates deterministic stub message IDs for testability
- Maintains an in-memory message store for stub mode
- Ready for real Slack REST API integration via urllib.request
- Formats alerts with severity-based color coding for Slack UI
"""

import json
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class SlackAdapter:
    """Slack notification adapter (stub)."""

    def __init__(self, webhook_url: str = "") -> None:
        """Initialize Slack adapter.

        Args:
            webhook_url: Slack webhook URL for incoming messages
        """
        self._webhook_url = webhook_url
        self._messages: dict[str, dict] = {}

    async def send_alert(
        self, title: str, message: str, severity: str, node_id: str = ""
    ) -> bool:
        """Send an alert to Slack.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (critical, high, medium, low)
            node_id: Optional node identifier

        Returns:
            True if alert sent successfully
        """
        message_id = f"SLACK-{uuid.uuid4().hex[:8].upper()}"

        severity_colors = {
            "critical": "#FF0000",  # Red
            "high": "#FF6600",  # Orange
            "medium": "#FFDD00",  # Yellow
            "low": "#0099FF",  # Blue
        }
        color = severity_colors.get(severity, "#808080")  # Default gray

        payload = {
            "message_id": message_id,
            "type": "alert",
            "title": title,
            "message": message,
            "severity": severity,
            "node_id": node_id,
            "color": color,
        }

        self._messages[message_id] = payload

        logger.info(
            "Slack send_alert (stub): %s - %s [severity=%s, node=%s, webhook=%s]",
            message_id,
            title,
            severity,
            node_id,
            self._webhook_url,
        )

        return True

    async def send_resolution(
        self, title: str, message: str, node_id: str = ""
    ) -> bool:
        """Send a resolution notification to Slack.

        Args:
            title: Resolution title
            message: Resolution details
            node_id: Optional node identifier

        Returns:
            True if resolution sent successfully
        """
        message_id = f"SLACK-{uuid.uuid4().hex[:8].upper()}"

        payload = {
            "message_id": message_id,
            "type": "resolution",
            "title": title,
            "message": message,
            "node_id": node_id,
            "color": "#00CC00",  # Green
        }

        self._messages[message_id] = payload

        logger.info(
            "Slack send_resolution (stub): %s - %s [node=%s, webhook=%s]",
            message_id,
            title,
            node_id,
            self._webhook_url,
        )

        return True

    def get_message(self, message_id: str) -> Optional[dict]:
        """Retrieve a sent message by ID (for testing).

        Args:
            message_id: Message ID to retrieve

        Returns:
            Message payload if found, None otherwise
        """
        return self._messages.get(message_id)
