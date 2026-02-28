"""
Playbook Entity Module

Architectural Intent:
- Defines the Playbook aggregate for remediation playbook marketplace
- Playbooks are immutable sequences of validated remediation steps
- Each step's command is validated against the agent allowlist to prevent
  arbitrary shell execution
- Frozen dataclasses enforce immutability and structural integrity

Domain Rules:
- All playbook step commands must use executables from ALLOWED_COMMANDS
- Steps are ordered and executed sequentially
- Each step may optionally trigger rollback on failure
- Playbooks are versioned and tagged for marketplace discovery
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import shlex

from chimera.infrastructure.agent.chimera_agent import ALLOWED_COMMANDS


@dataclass(frozen=True)
class PlaybookStep:
    """A single remediation step within a playbook.

    Attributes:
        name: Human-readable label for this step.
        command: Shell command to execute. The executable (first token)
                 must be present in the agent ALLOWED_COMMANDS allowlist.
        timeout: Maximum seconds to wait for the command to complete.
        rollback_on_failure: Whether to trigger rollback of prior steps
                             if this step fails.
    """

    name: str
    command: str
    timeout: int = 60
    rollback_on_failure: bool = True


@dataclass(frozen=True)
class Playbook:
    """Playbook aggregate root for the remediation marketplace.

    A playbook encapsulates a reproducible, validated sequence of
    remediation steps that can be shared, versioned, and executed
    across the Chimera fleet.

    Attributes:
        id: Unique identifier for this playbook.
        name: Human-readable playbook name.
        description: Detailed description of what this playbook remediates.
        author: Author or publisher of the playbook.
        version: Semantic version string (e.g. "1.0.0").
        tags: Tuple of tags for marketplace search and categorisation.
        steps: Ordered tuple of PlaybookStep instances.
        target_os: Target operating system (default "nixos").
    """

    id: str
    name: str
    description: str
    author: str
    version: str
    tags: tuple[str, ...]
    steps: tuple[PlaybookStep, ...]
    target_os: str = "nixos"

    @property
    def step_count(self) -> int:
        """Return the number of steps in this playbook."""
        return len(self.steps)

    def validate(self) -> list[str]:
        """Validate all steps use allowed commands.

        Checks every step's command against the agent ALLOWED_COMMANDS
        allowlist. Returns a list of human-readable error strings.
        An empty list means the playbook is valid.
        """
        errors: list[str] = []

        if not self.steps:
            errors.append("Playbook must contain at least one step")

        for i, step in enumerate(self.steps):
            if not step.name.strip():
                errors.append(f"Step {i}: name must not be empty")

            if not step.command.strip():
                errors.append(f"Step {i} ({step.name}): command must not be empty")
                continue

            try:
                parts = shlex.split(step.command)
            except ValueError as exc:
                errors.append(
                    f"Step {i} ({step.name}): invalid command syntax: {exc}"
                )
                continue

            if not parts:
                errors.append(f"Step {i} ({step.name}): command must not be empty")
                continue

            executable = os.path.basename(parts[0])
            if executable not in ALLOWED_COMMANDS:
                errors.append(
                    f"Step {i} ({step.name}): command '{executable}' "
                    f"not in allowlist. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
                )

            if step.timeout <= 0:
                errors.append(
                    f"Step {i} ({step.name}): timeout must be positive, "
                    f"got {step.timeout}"
                )

        return errors
