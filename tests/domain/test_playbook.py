"""
Playbook Entity Tests

Architectural Intent:
- Unit tests for Playbook and PlaybookStep domain entities
- Validates command allowlist enforcement
- Tests structural invariants (immutability, step_count)
- No mocks needed - pure domain logic testing
"""

import pytest

from chimera.domain.entities.playbook import Playbook, PlaybookStep


class TestPlaybookStep:
    """Tests for PlaybookStep value object."""

    def test_create_step_with_defaults(self):
        step = PlaybookStep(name="restart", command="systemctl restart foo")
        assert step.name == "restart"
        assert step.command == "systemctl restart foo"
        assert step.timeout == 60
        assert step.rollback_on_failure is True

    def test_create_step_with_custom_values(self):
        step = PlaybookStep(
            name="rebuild",
            command="nixos-rebuild switch",
            timeout=300,
            rollback_on_failure=False,
        )
        assert step.timeout == 300
        assert step.rollback_on_failure is False

    def test_step_is_frozen(self):
        step = PlaybookStep(name="restart", command="systemctl restart foo")
        with pytest.raises(AttributeError):
            step.name = "changed"


class TestPlaybook:
    """Tests for Playbook aggregate root."""

    def _make_valid_playbook(self, **overrides) -> Playbook:
        defaults = dict(
            id="test-1",
            name="Test Playbook",
            description="A test playbook",
            author="tester",
            version="1.0.0",
            tags=("test",),
            steps=(
                PlaybookStep(name="restart", command="systemctl restart foo"),
            ),
        )
        defaults.update(overrides)
        return Playbook(**defaults)

    def test_create_playbook(self):
        playbook = self._make_valid_playbook()
        assert playbook.id == "test-1"
        assert playbook.name == "Test Playbook"
        assert playbook.target_os == "nixos"

    def test_step_count(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(name="step1", command="systemctl restart a"),
                PlaybookStep(name="step2", command="systemctl restart b"),
                PlaybookStep(name="step3", command="nixos-rebuild switch"),
            )
        )
        assert playbook.step_count == 3

    def test_step_count_empty(self):
        playbook = self._make_valid_playbook(steps=())
        assert playbook.step_count == 0

    def test_playbook_is_frozen(self):
        playbook = self._make_valid_playbook()
        with pytest.raises(AttributeError):
            playbook.name = "changed"

    def test_validate_valid_playbook(self):
        playbook = self._make_valid_playbook()
        errors = playbook.validate()
        assert errors == []

    def test_validate_allowed_commands(self):
        """All commands in the agent allowlist should pass validation."""
        steps = (
            PlaybookStep(name="nix-env", command="nix-env --list"),
            PlaybookStep(name="nixos-rebuild", command="nixos-rebuild switch"),
            PlaybookStep(name="systemctl", command="systemctl restart foo"),
            PlaybookStep(name="nix-build", command="nix-build /etc/nixos"),
            PlaybookStep(name="nix-store", command="nix-store --query /nix/store/abc"),
        )
        playbook = self._make_valid_playbook(steps=steps)
        errors = playbook.validate()
        assert errors == []

    def test_validate_rejects_disallowed_command(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(name="bad step", command="rm -rf /"),
            )
        )
        errors = playbook.validate()
        assert len(errors) == 1
        assert "rm" in errors[0]
        assert "not in allowlist" in errors[0]

    def test_validate_rejects_multiple_bad_commands(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(name="bad1", command="curl http://evil.com"),
                PlaybookStep(name="good", command="systemctl restart foo"),
                PlaybookStep(name="bad2", command="bash -c 'echo pwned'"),
            )
        )
        errors = playbook.validate()
        assert len(errors) == 2
        assert any("curl" in e for e in errors)
        assert any("bash" in e for e in errors)

    def test_validate_rejects_empty_steps(self):
        playbook = self._make_valid_playbook(steps=())
        errors = playbook.validate()
        assert len(errors) == 1
        assert "at least one step" in errors[0]

    def test_validate_rejects_empty_command(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(name="empty", command=""),
            )
        )
        errors = playbook.validate()
        assert any("command must not be empty" in e for e in errors)

    def test_validate_rejects_empty_name(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(name="", command="systemctl restart foo"),
            )
        )
        errors = playbook.validate()
        assert any("name must not be empty" in e for e in errors)

    def test_validate_rejects_negative_timeout(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(
                    name="bad timeout",
                    command="systemctl restart foo",
                    timeout=-1,
                ),
            )
        )
        errors = playbook.validate()
        assert any("timeout must be positive" in e for e in errors)

    def test_validate_rejects_zero_timeout(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(
                    name="zero timeout",
                    command="systemctl restart foo",
                    timeout=0,
                ),
            )
        )
        errors = playbook.validate()
        assert any("timeout must be positive" in e for e in errors)

    def test_validate_command_with_path_prefix(self):
        """Commands with full paths should validate the basename."""
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(
                    name="full path",
                    command="/usr/bin/systemctl restart foo",
                ),
            )
        )
        errors = playbook.validate()
        assert errors == []

    def test_validate_command_with_bad_path_prefix(self):
        playbook = self._make_valid_playbook(
            steps=(
                PlaybookStep(
                    name="bad full path",
                    command="/usr/bin/rm -rf /",
                ),
            )
        )
        errors = playbook.validate()
        assert len(errors) == 1
        assert "rm" in errors[0]
