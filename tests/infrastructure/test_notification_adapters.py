"""Tests for notification adapters (Slack, Email, PagerDuty)."""

import pytest
from chimera.infrastructure.adapters.slack_adapter import SlackAdapter
from chimera.infrastructure.adapters.email_adapter import EmailAdapter
from chimera.infrastructure.adapters.pagerduty_adapter import PagerDutyAdapter
from chimera.domain.ports.notification_port import NotificationPort


class TestSlackAdapter:
    """Test Slack notification adapter."""

    @pytest.mark.asyncio
    async def test_send_alert_returns_true(self):
        """Test that send_alert returns True."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        result = await adapter.send_alert(
            title="High CPU Usage",
            message="CPU usage on node-01 is at 95%",
            severity="high",
            node_id="node-01",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_creates_message_id(self):
        """Test that send_alert creates a message ID."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        await adapter.send_alert(
            title="High CPU Usage",
            message="CPU usage on node-01 is at 95%",
            severity="high",
            node_id="node-01",
        )
        # Verify message was stored (indirectly by checking internal state)
        assert len(adapter._messages) == 1

    @pytest.mark.asyncio
    async def test_send_alert_with_all_severity_levels(self):
        """Test send_alert with all severity levels."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        severities = ["critical", "high", "medium", "low"]

        for severity in severities:
            result = await adapter.send_alert(
                title=f"{severity.upper()} alert",
                message="Test message",
                severity=severity,
                node_id="node-01",
            )
            assert result is True

        assert len(adapter._messages) == 4

    @pytest.mark.asyncio
    async def test_send_alert_without_node_id(self):
        """Test send_alert without optional node_id."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        result = await adapter.send_alert(
            title="Infrastructure alert",
            message="System-wide issue detected",
            severity="critical",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_resolution_returns_true(self):
        """Test that send_resolution returns True."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        result = await adapter.send_resolution(
            title="CPU Issue Resolved",
            message="CPU usage returned to normal",
            node_id="node-01",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_resolution_creates_message_id(self):
        """Test that send_resolution creates a message ID."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        await adapter.send_resolution(
            title="CPU Issue Resolved",
            message="CPU usage returned to normal",
            node_id="node-01",
        )
        assert len(adapter._messages) == 1

    @pytest.mark.asyncio
    async def test_send_resolution_without_node_id(self):
        """Test send_resolution without optional node_id."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        result = await adapter.send_resolution(
            title="System Issue Resolved",
            message="All systems operational",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get_message_after_send_alert(self):
        """Test retrieving a message after sending an alert."""
        adapter = SlackAdapter(webhook_url="https://hooks.slack.com/services/...")
        await adapter.send_alert(
            title="Test Alert",
            message="Test message",
            severity="high",
            node_id="node-01",
        )
        message_id = list(adapter._messages.keys())[0]
        message = adapter.get_message(message_id)
        assert message is not None
        assert message["type"] == "alert"
        assert message["title"] == "Test Alert"
        assert message["severity"] == "high"

    @pytest.mark.asyncio
    async def test_get_message_not_found(self):
        """Test retrieving a non-existent message."""
        adapter = SlackAdapter()
        result = adapter.get_message("SLACK-NONEXIST")
        assert result is None

    def test_slack_implements_notification_port(self):
        """Test that SlackAdapter implements NotificationPort."""
        adapter = SlackAdapter()
        assert isinstance(adapter, NotificationPort)


class TestEmailAdapter:
    """Test Email notification adapter."""

    @pytest.mark.asyncio
    async def test_send_alert_returns_true(self):
        """Test that send_alert returns True."""
        adapter = EmailAdapter(
            smtp_host="smtp.example.com",
            smtp_port=587,
            recipients=["alerts@example.com"],
        )
        result = await adapter.send_alert(
            title="Disk Full",
            message="Root partition is at 95% capacity",
            severity="high",
            node_id="node-02",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_creates_message_id(self):
        """Test that send_alert creates a message ID."""
        adapter = EmailAdapter(recipients=["alerts@example.com"])
        await adapter.send_alert(
            title="Disk Full",
            message="Root partition is at 95% capacity",
            severity="high",
            node_id="node-02",
        )
        assert len(adapter._messages) == 1

    @pytest.mark.asyncio
    async def test_send_alert_with_multiple_recipients(self):
        """Test send_alert with multiple recipients."""
        recipients = ["alert1@example.com", "alert2@example.com", "alert3@example.com"]
        adapter = EmailAdapter(recipients=recipients)
        await adapter.send_alert(
            title="Service Down",
            message="Web service is unreachable",
            severity="critical",
            node_id="node-03",
        )
        message_id = list(adapter._messages.keys())[0]
        message = adapter.get_message(message_id)
        assert message["recipients"] == recipients

    @pytest.mark.asyncio
    async def test_send_alert_without_node_id(self):
        """Test send_alert without optional node_id."""
        adapter = EmailAdapter(recipients=["alerts@example.com"])
        result = await adapter.send_alert(
            title="System Alert",
            message="Important system notification",
            severity="medium",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_resolution_returns_true(self):
        """Test that send_resolution returns True."""
        adapter = EmailAdapter(recipients=["alerts@example.com"])
        result = await adapter.send_resolution(
            title="Disk Full - Resolved",
            message="Partition cleanup completed",
            node_id="node-02",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_resolution_creates_message_id(self):
        """Test that send_resolution creates a message ID."""
        adapter = EmailAdapter(recipients=["alerts@example.com"])
        await adapter.send_resolution(
            title="Disk Full - Resolved",
            message="Partition cleanup completed",
            node_id="node-02",
        )
        assert len(adapter._messages) == 1

    @pytest.mark.asyncio
    async def test_send_resolution_without_node_id(self):
        """Test send_resolution without optional node_id."""
        adapter = EmailAdapter(recipients=["alerts@example.com"])
        result = await adapter.send_resolution(
            title="System Issue Resolved",
            message="All services restored",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get_message_after_send_resolution(self):
        """Test retrieving a message after sending a resolution."""
        adapter = EmailAdapter(recipients=["alerts@example.com"])
        await adapter.send_resolution(
            title="Issue Resolved",
            message="Resolution details",
            node_id="node-02",
        )
        message_id = list(adapter._messages.keys())[0]
        message = adapter.get_message(message_id)
        assert message is not None
        assert message["type"] == "resolution"
        assert "[RESOLVED]" in message["subject"]

    @pytest.mark.asyncio
    async def test_get_message_not_found(self):
        """Test retrieving a non-existent message."""
        adapter = EmailAdapter()
        result = adapter.get_message("EMAIL-NONEXIST")
        assert result is None

    @pytest.mark.asyncio
    async def test_email_with_empty_recipients(self):
        """Test email adapter with no recipients configured."""
        adapter = EmailAdapter(recipients=[])
        result = await adapter.send_alert(
            title="Alert",
            message="Message",
            severity="high",
        )
        assert result is True

    def test_email_implements_notification_port(self):
        """Test that EmailAdapter implements NotificationPort."""
        adapter = EmailAdapter()
        assert isinstance(adapter, NotificationPort)


class TestPagerDutyAdapter:
    """Test PagerDuty notification adapter."""

    @pytest.mark.asyncio
    async def test_send_alert_returns_true(self):
        """Test that send_alert returns True."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        result = await adapter.send_alert(
            title="Database connection lost",
            message="Unable to connect to primary database",
            severity="critical",
            node_id="db-node-01",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_creates_incident_id(self):
        """Test that send_alert creates an incident ID."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        await adapter.send_alert(
            title="Database connection lost",
            message="Unable to connect to primary database",
            severity="critical",
            node_id="db-node-01",
        )
        assert len(adapter._incidents) == 1

    @pytest.mark.asyncio
    async def test_send_alert_maps_severity_to_urgency(self):
        """Test that severity levels map correctly to PagerDuty urgency."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")

        # Critical and high map to "high" urgency
        await adapter.send_alert(
            title="Critical Alert",
            message="Message",
            severity="critical",
        )
        await adapter.send_alert(
            title="High Alert",
            message="Message",
            severity="high",
        )
        # Medium and low map to "low" urgency
        await adapter.send_alert(
            title="Medium Alert",
            message="Message",
            severity="medium",
        )
        await adapter.send_alert(
            title="Low Alert",
            message="Message",
            severity="low",
        )

        incidents = list(adapter._incidents.values())
        assert incidents[0]["urgency"] == "high"  # critical
        assert incidents[1]["urgency"] == "high"  # high
        assert incidents[2]["urgency"] == "low"  # medium
        assert incidents[3]["urgency"] == "low"  # low

    @pytest.mark.asyncio
    async def test_send_alert_without_node_id(self):
        """Test send_alert without optional node_id."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        result = await adapter.send_alert(
            title="Infrastructure alert",
            message="System-wide issue",
            severity="high",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_resolution_returns_true(self):
        """Test that send_resolution returns True."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        result = await adapter.send_resolution(
            title="Database connection restored",
            message="Primary database is now responsive",
            node_id="db-node-01",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_resolution_creates_incident_id(self):
        """Test that send_resolution creates an incident ID."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        await adapter.send_resolution(
            title="Database connection restored",
            message="Primary database is now responsive",
            node_id="db-node-01",
        )
        assert len(adapter._incidents) == 1

    @pytest.mark.asyncio
    async def test_send_resolution_without_node_id(self):
        """Test send_resolution without optional node_id."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        result = await adapter.send_resolution(
            title="System Issue Resolved",
            message="All services operational",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get_incident_after_send_alert(self):
        """Test retrieving an incident after sending an alert."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        await adapter.send_alert(
            title="Test Alert",
            message="Test message",
            severity="high",
            node_id="node-01",
        )
        incident_id = list(adapter._incidents.keys())[0]
        incident = adapter.get_incident(incident_id)
        assert incident is not None
        assert incident["type"] == "alert"
        assert incident["title"] == "Test Alert"
        assert incident["status"] == "triggered"

    @pytest.mark.asyncio
    async def test_get_incident_after_send_resolution(self):
        """Test retrieving an incident after sending a resolution."""
        adapter = PagerDutyAdapter(integration_key="test-key-123")
        await adapter.send_resolution(
            title="Test Resolution",
            message="Issue resolved",
            node_id="node-01",
        )
        incident_id = list(adapter._incidents.keys())[0]
        incident = adapter.get_incident(incident_id)
        assert incident is not None
        assert incident["type"] == "resolution"
        assert incident["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self):
        """Test retrieving a non-existent incident."""
        adapter = PagerDutyAdapter()
        result = adapter.get_incident("PD-NONEXIST")
        assert result is None

    def test_pagerduty_implements_notification_port(self):
        """Test that PagerDutyAdapter implements NotificationPort."""
        adapter = PagerDutyAdapter()
        assert isinstance(adapter, NotificationPort)


class TestNotificationPortAdapters:
    """Integration tests for all adapters implementing NotificationPort."""

    def test_all_adapters_implement_port(self):
        """Verify all adapters properly implement NotificationPort."""
        adapters = [
            SlackAdapter(),
            EmailAdapter(),
            PagerDutyAdapter(),
        ]

        for adapter in adapters:
            assert isinstance(adapter, NotificationPort), (
                f"{adapter.__class__.__name__} does not implement NotificationPort"
            )

    @pytest.mark.asyncio
    async def test_all_adapters_send_alert(self):
        """Test that all adapters can send alerts."""
        adapters = [
            SlackAdapter(),
            EmailAdapter(),
            PagerDutyAdapter(),
        ]

        for adapter in adapters:
            result = await adapter.send_alert(
                title="Test Alert",
                message="Test message",
                severity="high",
                node_id="node-01",
            )
            assert result is True, f"{adapter.__class__.__name__}.send_alert failed"

    @pytest.mark.asyncio
    async def test_all_adapters_send_resolution(self):
        """Test that all adapters can send resolutions."""
        adapters = [
            SlackAdapter(),
            EmailAdapter(),
            PagerDutyAdapter(),
        ]

        for adapter in adapters:
            result = await adapter.send_resolution(
                title="Test Resolution",
                message="Test message",
                node_id="node-01",
            )
            assert (
                result is True
            ), f"{adapter.__class__.__name__}.send_resolution failed"
