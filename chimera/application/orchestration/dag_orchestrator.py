"""
Workflow Orchestration Module

Architectural Intent:
- DAG-based workflow execution for multi-step deployment processes
- Automatically parallelizes independent steps
- Enforces dependency ordering
- Supports backpressure and rate limiting at orchestration layer

Parallelization Strategy:
- All steps at the same dependency level execute concurrently
- Results from previous steps are available to dependent steps
- Failures in critical steps propagate to dependent steps
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any


@dataclass
class WorkflowStep:
    name: str
    execute: Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]
    depends_on: list[str] = field(default_factory=list)
    is_critical: bool = True


class OrchestrationError(Exception):
    pass


class DAGOrchestrator:
    def __init__(self, steps: list[WorkflowStep]) -> None:
        self.steps: dict[str, WorkflowStep] = {s.name: s for s in steps}
        self._validated = False

    def _validate_no_cycles(self) -> None:
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(name: str) -> bool:
            visited.add(name)
            rec_stack.add(name)

            step = self.steps.get(name)
            if step:
                for dep in step.depends_on:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(name)
            return False

        for step_name in self.steps:
            if step_name not in visited:
                if has_cycle(step_name):
                    raise OrchestrationError(
                        f"Circular dependency detected involving step: {step_name}"
                    )

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self._validated:
            self._validate_no_cycles()
            self._validated = True

        completed: dict[str, Any] = {}
        pending = set(self.steps.keys())

        while pending:
            ready = [
                name
                for name in pending
                if all(dep in completed for dep in self.steps[name].depends_on)
            ]
            if not ready:
                raise OrchestrationError(
                    f"Circular dependency or unsatisfied dependencies. Pending: {pending}"
                )

            results = await asyncio.gather(
                *(self.steps[name].execute(context, completed) for name in ready),
                return_exceptions=True,
            )

            for name, result in zip(ready, results):
                if isinstance(result, Exception):
                    if self.steps[name].is_critical:
                        raise OrchestrationError(
                            f"Critical step {name} failed: {result}"
                        )
                    completed[name] = result
                else:
                    completed[name] = result
                pending.discard(name)

        return completed
