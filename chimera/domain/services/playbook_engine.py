"""
Playbook Engine Service

Architectural Intent:
- Domain service responsible for executing remediation playbooks
- Executes steps sequentially, tracking execution state at each phase
- Supports automatic rollback on step failure when configured
- All commands are re-validated against the agent allowlist before execution

Execution Model:
1. Validate the entire playbook before starting
2. Execute each step in order, recording results
3. On step failure with rollback_on_failure=True, execute rollback
   of all previously completed steps in reverse order
4. Produce a final execution result with per-step outcomes

Security:
- Commands validated against ALLOWED_COMMANDS at execution time
- Subprocess execution uses shlex-parsed argument lists (no shell=True)
- Each step is subject to its configured timeout
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto
from typing import Optional

from chimera.domain.entities.playbook import Playbook, PlaybookStep
from chimera.infrastructure.agent.chimera_agent import ALLOWED_COMMANDS

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Execution status for an individual playbook step."""

    PENDING = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    ROLLED_BACK = auto()
    SKIPPED = auto()


class PlaybookExecutionStatus(Enum):
    """Overall execution status for a playbook run."""

    PENDING = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    ROLLED_BACK = auto()


@dataclass
class StepResult:
    """Result of executing a single playbook step.

    Attributes:
        step: The PlaybookStep that was executed.
        status: Final status of this step.
        started_at: Timestamp when execution began.
        completed_at: Timestamp when execution finished.
        output: Captured stdout from the command.
        error: Captured stderr or error message.
        return_code: Process exit code, or None if not executed.
    """

    step: PlaybookStep
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: str = ""
    error: str = ""
    return_code: Optional[int] = None


@dataclass
class PlaybookExecutionResult:
    """Aggregate result of a full playbook execution.

    Attributes:
        playbook: The playbook that was executed.
        status: Overall execution status.
        step_results: Per-step results in execution order.
        started_at: Timestamp when playbook execution began.
        completed_at: Timestamp when playbook execution finished.
    """

    playbook: Playbook
    status: PlaybookExecutionStatus = PlaybookExecutionStatus.PENDING
    step_results: list[StepResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def succeeded_steps(self) -> int:
        """Count of steps that completed successfully."""
        return sum(1 for r in self.step_results if r.status == StepStatus.SUCCEEDED)

    @property
    def failed_steps(self) -> int:
        """Count of steps that failed."""
        return sum(1 for r in self.step_results if r.status == StepStatus.FAILED)


class PlaybookEngine:
    """Domain service for executing remediation playbooks.

    Executes playbook steps sequentially with validation, timeout
    enforcement, and optional rollback on failure. All commands are
    validated against the agent ALLOWED_COMMANDS allowlist before
    execution.
    """

    def _validate_command(self, command: str) -> list[str]:
        """Parse and validate a command against the allowlist.

        Returns the parsed command as a list of arguments.
        Raises ValueError if the command is not allowed.
        """
        parts = shlex.split(command)
        if not parts:
            raise ValueError("Empty command")

        executable = os.path.basename(parts[0])
        if executable not in ALLOWED_COMMANDS:
            raise ValueError(
                f"Command '{executable}' not in allowlist. "
                f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
            )
        return parts

    async def execute(self, playbook: Playbook) -> PlaybookExecutionResult:
        """Execute a playbook step by step.

        Validates the playbook first, then runs each step sequentially.
        If a step fails and has rollback_on_failure enabled, all previously
        succeeded steps are rolled back in reverse order.

        Args:
            playbook: The Playbook to execute.

        Returns:
            PlaybookExecutionResult with per-step outcomes.
        """
        errors = playbook.validate()
        if errors:
            result = PlaybookExecutionResult(
                playbook=playbook,
                status=PlaybookExecutionStatus.FAILED,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            result.step_results = [
                StepResult(
                    step=step,
                    status=StepStatus.SKIPPED,
                    error="Playbook validation failed",
                )
                for step in playbook.steps
            ]
            return result

        result = PlaybookExecutionResult(
            playbook=playbook,
            status=PlaybookExecutionStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        completed_steps: list[StepResult] = []

        for step in playbook.steps:
            step_result = await self._execute_step(step)
            result.step_results.append(step_result)

            if step_result.status == StepStatus.SUCCEEDED:
                completed_steps.append(step_result)
            elif step_result.status == StepStatus.FAILED:
                logger.warning(
                    "Playbook '%s' step '%s' failed: %s",
                    playbook.name,
                    step.name,
                    step_result.error,
                )

                if step.rollback_on_failure and completed_steps:
                    logger.info(
                        "Rolling back %d completed steps", len(completed_steps)
                    )
                    await self._rollback(completed_steps, result)
                    result.status = PlaybookExecutionStatus.ROLLED_BACK
                else:
                    result.status = PlaybookExecutionStatus.FAILED

                # Mark remaining steps as skipped
                remaining_idx = len(result.step_results)
                for remaining_step in playbook.steps[remaining_idx:]:
                    result.step_results.append(
                        StepResult(
                            step=remaining_step,
                            status=StepStatus.SKIPPED,
                            error="Skipped due to prior step failure",
                        )
                    )
                break
        else:
            result.status = PlaybookExecutionStatus.SUCCEEDED

        result.completed_at = datetime.now(UTC)
        return result

    async def _execute_step(self, step: PlaybookStep) -> StepResult:
        """Execute a single playbook step.

        Validates the command, runs it as a subprocess with the
        configured timeout, and captures output.
        """
        step_result = StepResult(
            step=step,
            status=StepStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        try:
            cmd_parts = self._validate_command(step.command)
        except ValueError as exc:
            step_result.status = StepStatus.FAILED
            step_result.error = str(exc)
            step_result.completed_at = datetime.now(UTC)
            return step_result

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=step.timeout,
            )

            step_result.output = stdout.decode() if stdout else ""
            step_result.error = stderr.decode() if stderr else ""
            step_result.return_code = proc.returncode

            if proc.returncode == 0:
                step_result.status = StepStatus.SUCCEEDED
            else:
                step_result.status = StepStatus.FAILED
                logger.warning(
                    "Step '%s' exited with code %d: %s",
                    step.name,
                    proc.returncode,
                    step_result.error,
                )

        except asyncio.TimeoutError:
            step_result.status = StepStatus.FAILED
            step_result.error = f"Step timed out after {step.timeout}s"
            logger.warning("Step '%s' timed out after %ds", step.name, step.timeout)

        except Exception as exc:
            step_result.status = StepStatus.FAILED
            step_result.error = str(exc)
            logger.error("Step '%s' execution error: %s", step.name, exc)

        step_result.completed_at = datetime.now(UTC)
        return step_result

    async def _rollback(
        self,
        completed_steps: list[StepResult],
        result: PlaybookExecutionResult,
    ) -> None:
        """Roll back completed steps in reverse order.

        For each successfully completed step, marks it as ROLLED_BACK.
        Rollback is best-effort; failures are logged but do not halt
        the rollback sequence.
        """
        for step_result in reversed(completed_steps):
            logger.info("Rolling back step: %s", step_result.step.name)
            step_result.status = StepStatus.ROLLED_BACK
