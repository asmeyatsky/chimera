"""
Notification Port

Architectural Intent:
- Abstract interface for sending alerts and resolutions
- Allows decoupling of notification producers from channels (Slack, Email, PagerDuty, etc.)
- Enables multi-channel notification without domain knowledge of specific providers

Design Decisions:
- Uses Protocol for structural typing (no inheritance needed)
- send_alert: For incident/alert notifications with severity levels
- send_resolution: For resolved/closed notifications
- Methods return bool to indicate success/failure
- node_id is optional to support infrastructure-wide notifications
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationPort(Protocol):
    """Port for sending alerts and resolutions through external notification channels."""

    async def send_alert(
        self, title: str, message: str, severity: str, node_id: str = ""
    ) -> bool:
        """Send an alert notification.

        Args:
            title: Alert title/subject
            message: Detailed alert message
            severity: Severity level (critical, high, medium, low)
            node_id: Optional node/instance identifier

        Returns:
            True if notification sent successfully, False otherwise
        """
        ...

    async def send_resolution(
        self, title: str, message: str, node_id: str = ""
    ) -> bool:
        """Send a resolution notification.

        Args:
            title: Resolution title/subject
            message: Resolution details
            node_id: Optional node/instance identifier

        Returns:
            True if notification sent successfully, False otherwise
        """
        ...
