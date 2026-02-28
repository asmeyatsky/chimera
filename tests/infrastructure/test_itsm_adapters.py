"""Tests for ITSM adapters (ServiceNow and Jira)."""

import pytest
from chimera.infrastructure.adapters.servicenow_adapter import ServiceNowAdapter
from chimera.infrastructure.adapters.jira_adapter import JiraAdapter
from chimera.domain.ports.itsm_port import ITSMPort


class TestServiceNowAdapter:
    @pytest.mark.asyncio
    async def test_create_incident_returns_ticket_id(self):
        adapter = ServiceNowAdapter()
        ticket_id = await adapter.create_incident(
            title="Disk full",
            description="Root partition at 95%",
            severity="high",
            node_id="node-01",
        )
        assert ticket_id.startswith("SNW-")
        assert len(ticket_id) == 12  # "SNW-" + 8 hex chars

    @pytest.mark.asyncio
    async def test_update_incident(self):
        adapter = ServiceNowAdapter()
        ticket_id = await adapter.create_incident(
            title="CPU spike",
            description="CPU at 100%",
            severity="critical",
            node_id="node-02",
        )
        await adapter.update_incident(ticket_id, "in_progress", "Investigating")
        incident = await adapter.get_incident(ticket_id)
        assert incident is not None
        assert incident["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_resolve_incident(self):
        adapter = ServiceNowAdapter()
        ticket_id = await adapter.create_incident(
            title="Service down",
            description="Web service unreachable",
            severity="high",
            node_id="node-03",
        )
        await adapter.resolve_incident(ticket_id, "Restarted service")
        incident = await adapter.get_incident(ticket_id)
        assert incident is not None
        assert incident["status"] == "resolved"
        assert incident["resolution"] == "Restarted service"

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self):
        adapter = ServiceNowAdapter()
        result = await adapter.get_incident("SNW-NONEXIST")
        assert result is None

    def test_implements_itsm_port(self):
        adapter = ServiceNowAdapter()
        assert isinstance(adapter, ITSMPort)


class TestJiraAdapter:
    @pytest.mark.asyncio
    async def test_create_incident_returns_ticket_id(self):
        adapter = JiraAdapter()
        ticket_id = await adapter.create_incident(
            title="Disk full",
            description="Root partition at 95%",
            severity="high",
            node_id="node-01",
        )
        assert ticket_id.startswith("JIRA-")
        assert len(ticket_id) == 13  # "JIRA-" + 8 hex chars

    @pytest.mark.asyncio
    async def test_update_incident(self):
        adapter = JiraAdapter()
        ticket_id = await adapter.create_incident(
            title="CPU spike",
            description="CPU at 100%",
            severity="critical",
            node_id="node-02",
        )
        await adapter.update_incident(ticket_id, "in_progress", "Investigating")
        incident = await adapter.get_incident(ticket_id)
        assert incident is not None
        assert incident["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_resolve_incident(self):
        adapter = JiraAdapter()
        ticket_id = await adapter.create_incident(
            title="Service down",
            description="Web service unreachable",
            severity="high",
            node_id="node-03",
        )
        await adapter.resolve_incident(ticket_id, "Restarted service")
        incident = await adapter.get_incident(ticket_id)
        assert incident is not None
        assert incident["status"] == "resolved"
        assert incident["resolution"] == "Restarted service"

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self):
        adapter = JiraAdapter()
        result = await adapter.get_incident("JIRA-NONEXIST")
        assert result is None

    def test_implements_itsm_port(self):
        adapter = JiraAdapter()
        assert isinstance(adapter, ITSMPort)
