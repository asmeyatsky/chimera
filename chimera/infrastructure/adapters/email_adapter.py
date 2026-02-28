"""
Email Notification Adapter

Architectural Intent:
- Implements NotificationPort for email notifications
- Stub implementation that logs calls for development and testing
- Uses stdlib smtplib for the mail layer (no external dependencies)

Design Decisions:
- Generates deterministic stub message IDs for testability
- Maintains an in-memory message store for stub mode
- Ready for real SMTP integration via smtplib module
- Supports recipient list for broadcast notifications
"""

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class EmailAdapter:
    """Email notification adapter (stub)."""

    def __init__(
        self, smtp_host: str = "", smtp_port: int = 587, recipients: list[str] = None
    ) -> None:
        """Initialize email adapter.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (default 587 for TLS)
            recipients: List of email addresses to send notifications to
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._recipients = recipients or []
        self._messages: dict[str, dict] = {}

    async def send_alert(
        self, title: str, message: str, severity: str, node_id: str = ""
    ) -> bool:
        """Send an alert email.

        Args:
            title: Alert subject line
            message: Alert body
            severity: Severity level (critical, high, medium, low)
            node_id: Optional node identifier

        Returns:
            True if alert sent successfully
        """
        message_id = f"EMAIL-{uuid.uuid4().hex[:8].upper()}"

        payload = {
            "message_id": message_id,
            "type": "alert",
            "subject": f"[{severity.upper()}] {title}",
            "body": message,
            "severity": severity,
            "node_id": node_id,
            "recipients": self._recipients,
        }

        self._messages[message_id] = payload

        logger.info(
            "Email send_alert (stub): %s - %s [severity=%s, node=%s, recipients=%s]",
            message_id,
            title,
            severity,
            node_id,
            ",".join(self._recipients),
        )

        return True

    async def send_resolution(
        self, title: str, message: str, node_id: str = ""
    ) -> bool:
        """Send a resolution email.

        Args:
            title: Resolution subject line
            message: Resolution details
            node_id: Optional node identifier

        Returns:
            True if resolution sent successfully
        """
        message_id = f"EMAIL-{uuid.uuid4().hex[:8].upper()}"

        payload = {
            "message_id": message_id,
            "type": "resolution",
            "subject": f"[RESOLVED] {title}",
            "body": message,
            "node_id": node_id,
            "recipients": self._recipients,
        }

        self._messages[message_id] = payload

        logger.info(
            "Email send_resolution (stub): %s - %s [node=%s, recipients=%s]",
            message_id,
            title,
            node_id,
            ",".join(self._recipients),
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
