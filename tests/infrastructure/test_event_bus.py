"""Tests for EventBus infrastructure."""

import pytest
from chimera.infrastructure.event_bus import EventBus
from chimera.domain.events.event_base import DomainEvent
from chimera.domain.entities.deployment import DeploymentStartedEvent


class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_to_subscriber(self):
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(DeploymentStartedEvent, handler)

        event = DeploymentStartedEvent(
            aggregate_id="test", session_id="s1", config_path="/etc/nix"
        )
        await bus.publish([event])

        assert len(received) == 1
        assert received[0].aggregate_id == "test"

    @pytest.mark.asyncio
    async def test_no_subscriber(self):
        bus = EventBus()
        event = DeploymentStartedEvent(aggregate_id="test")
        # Should not raise
        await bus.publish([event])

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = EventBus()
        received_a = []
        received_b = []

        async def handler_a(event):
            received_a.append(event)

        async def handler_b(event):
            received_b.append(event)

        bus.subscribe(DeploymentStartedEvent, handler_a)
        bus.subscribe(DeploymentStartedEvent, handler_b)

        event = DeploymentStartedEvent(aggregate_id="test")
        await bus.publish([event])

        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_type_filtering(self):
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(DeploymentStartedEvent, handler)

        # Publish a base DomainEvent — handler should NOT fire
        event = DomainEvent(aggregate_id="test")
        await bus.publish([event])

        assert len(received) == 0
