"""
Application Layer Tests

Architectural Intent:
- Tests for application use cases and orchestration
- Mocks used for port dependencies
- Verifies orchestration logic
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from chimera.application.orchestration.dag_orchestrator import (
    DAGOrchestrator,
    WorkflowStep,
    OrchestrationError,
)


class TestDAGOrchestrator:
    """Tests for DAG-based workflow orchestration."""

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        execution_order = []

        async def step_a(context, results):
            execution_order.append("a")
            return "a_result"

        async def step_b(context, results):
            execution_order.append("b")
            return "b_result"

        orchestrator = DAGOrchestrator(
            [
                WorkflowStep("a", step_a, depends_on=[]),
                WorkflowStep("b", step_b, depends_on=["a"]),
            ]
        )

        result = await orchestrator.execute({})

        assert execution_order == ["a", "b"]
        assert result["a"] == "a_result"
        assert result["b"] == "b_result"

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        execution_order = []

        async def step_a(context, results):
            execution_order.append("a_start")
            return "a_result"

        async def step_b(context, results):
            execution_order.append("b_start")
            return "b_result"

        orchestrator = DAGOrchestrator(
            [
                WorkflowStep("a", step_a, depends_on=[]),
                WorkflowStep("b", step_b, depends_on=[]),
            ]
        )

        result = await orchestrator.execute({})

        assert set(execution_order) == {"a_start", "b_start"}
        assert result["a"] == "a_result"
        assert result["b"] == "b_result"

    @pytest.mark.asyncio
    async def test_fan_out_fan_in(self):
        results_list = []

        async def step_a(context, results):
            return "a"

        async def step_b(context, results):
            return "b"

        async def step_c(context, results):
            results_list.append(results["a"])
            results_list.append(results["b"])
            return "c"

        orchestrator = DAGOrchestrator(
            [
                WorkflowStep("a", step_a, depends_on=[]),
                WorkflowStep("b", step_b, depends_on=[]),
                WorkflowStep("c", step_c, depends_on=["a", "b"]),
            ]
        )

        result = await orchestrator.execute({})

        assert result["c"] == "c"
        assert results_list == ["a", "b"]

    @pytest.mark.asyncio
    async def test_critical_failure_aborts(self):
        async def step_a(context, results):
            return "a"

        async def step_b(context, results):
            raise ValueError("Step B failed")

        orchestrator = DAGOrchestrator(
            [
                WorkflowStep("a", step_a, depends_on=[]),
                WorkflowStep("b", step_b, depends_on=["a"], is_critical=True),
            ]
        )

        with pytest.raises(OrchestrationError, match="Critical step b failed"):
            await orchestrator.execute({})

    @pytest.mark.asyncio
    async def test_non_critical_failure_continues(self):
        async def step_a(context, results):
            return "a"

        async def step_b(context, results):
            raise ValueError("Step B failed")

        orchestrator = DAGOrchestrator(
            [
                WorkflowStep("a", step_a, depends_on=[]),
                WorkflowStep("b", step_b, depends_on=["a"], is_critical=False),
            ]
        )

        result = await orchestrator.execute({})

        assert result["a"] == "a"
        assert isinstance(result["b"], ValueError)

    @pytest.mark.asyncio
    async def test_circular_dependency_detected(self):
        async def step_a(context, results):
            return "a"

        async def step_b(context, results):
            return "b"

        orchestrator = DAGOrchestrator(
            [
                WorkflowStep("a", step_a, depends_on=["b"]),
                WorkflowStep("b", step_b, depends_on=["a"]),
            ]
        )

        with pytest.raises(OrchestrationError, match="Circular dependency"):
            await orchestrator.execute({})
