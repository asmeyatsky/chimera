"""
Playbook Repository

Architectural Intent:
- In-memory repository for storing and retrieving remediation playbooks
- Provides search capabilities by tags for marketplace discovery
- Ships with built-in playbooks for common remediation scenarios
- Acts as the persistence adapter for the playbook marketplace

Built-in Playbooks:
- rollback: Roll back to the previous NixOS generation
- restart-service: Restart a failed systemd service
- rebuild: Full NixOS rebuild from current configuration
"""

from __future__ import annotations

from typing import Optional

from chimera.domain.entities.playbook import Playbook, PlaybookStep


def _builtin_playbooks() -> list[Playbook]:
    """Create the set of built-in remediation playbooks."""
    return [
        Playbook(
            id="builtin-rollback",
            name="rollback",
            description=(
                "Roll back to the previous NixOS generation. "
                "Use when a deployment introduces a regression or "
                "critical drift is detected."
            ),
            author="chimera",
            version="1.0.0",
            tags=("rollback", "recovery", "nixos"),
            steps=(
                PlaybookStep(
                    name="Switch to previous generation",
                    command="nixos-rebuild switch --rollback",
                    timeout=120,
                    rollback_on_failure=False,
                ),
                PlaybookStep(
                    name="Verify system health",
                    command="systemctl is-system-running",
                    timeout=30,
                    rollback_on_failure=False,
                ),
            ),
            target_os="nixos",
        ),
        Playbook(
            id="builtin-restart-service",
            name="restart-service",
            description=(
                "Restart a failed systemd service. "
                "Use when a service has entered a failed state "
                "and a simple restart is sufficient to remediate."
            ),
            author="chimera",
            version="1.0.0",
            tags=("restart", "service", "systemd", "remediation"),
            steps=(
                PlaybookStep(
                    name="Restart the target service",
                    command="systemctl restart chimera-agent",
                    timeout=60,
                    rollback_on_failure=True,
                ),
                PlaybookStep(
                    name="Verify service is active",
                    command="systemctl is-active chimera-agent",
                    timeout=15,
                    rollback_on_failure=False,
                ),
            ),
            target_os="nixos",
        ),
        Playbook(
            id="builtin-rebuild",
            name="rebuild",
            description=(
                "Perform a full NixOS rebuild from the current configuration. "
                "Use when significant drift is detected and a clean rebuild "
                "is the safest remediation path."
            ),
            author="chimera",
            version="1.0.0",
            tags=("rebuild", "nixos", "remediation", "full"),
            steps=(
                PlaybookStep(
                    name="Build new system configuration",
                    command="nix-build /etc/nixos/default.nix",
                    timeout=300,
                    rollback_on_failure=True,
                ),
                PlaybookStep(
                    name="Switch to new configuration",
                    command="nixos-rebuild switch",
                    timeout=120,
                    rollback_on_failure=True,
                ),
                PlaybookStep(
                    name="Verify system health",
                    command="systemctl is-system-running",
                    timeout=30,
                    rollback_on_failure=False,
                ),
            ),
            target_os="nixos",
        ),
    ]


class PlaybookRepository:
    """In-memory repository for remediation playbooks.

    Stores playbooks in a dictionary keyed by playbook ID.
    Initialised with a set of built-in playbooks that cover
    common remediation scenarios.
    """

    def __init__(self) -> None:
        self._playbooks: dict[str, Playbook] = {}
        for playbook in _builtin_playbooks():
            self._playbooks[playbook.id] = playbook

    def add(self, playbook: Playbook) -> None:
        """Store a playbook. Overwrites if the ID already exists."""
        self._playbooks[playbook.id] = playbook

    def get(self, playbook_id: str) -> Optional[Playbook]:
        """Retrieve a playbook by its unique ID."""
        return self._playbooks.get(playbook_id)

    def get_by_name(self, name: str) -> Optional[Playbook]:
        """Retrieve the first playbook matching the given name."""
        for playbook in self._playbooks.values():
            if playbook.name == name:
                return playbook
        return None

    def remove(self, playbook_id: str) -> bool:
        """Remove a playbook by ID. Returns True if it existed."""
        return self._playbooks.pop(playbook_id, None) is not None

    def list_all(self) -> list[Playbook]:
        """Return all stored playbooks."""
        return list(self._playbooks.values())

    def search_by_tags(self, tags: list[str]) -> list[Playbook]:
        """Return playbooks that match any of the given tags.

        A playbook matches if it contains at least one of the
        requested tags.
        """
        tag_set = set(tags)
        return [
            playbook
            for playbook in self._playbooks.values()
            if tag_set & set(playbook.tags)
        ]

    def search_by_all_tags(self, tags: list[str]) -> list[Playbook]:
        """Return playbooks that match all of the given tags.

        A playbook matches only if it contains every one of the
        requested tags.
        """
        tag_set = set(tags)
        return [
            playbook
            for playbook in self._playbooks.values()
            if tag_set <= set(playbook.tags)
        ]
