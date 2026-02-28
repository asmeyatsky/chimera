"""
Playbook Engine Tests

Architectural Intent:
- Unit tests for PlaybookEngine domain service
- Tests execution flow, rollback behaviour, and validation gating
- Uses subprocess mocking to avoid real command execution
- Verifies security enforcement (allowlist) at execution time
"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from chimera.domain.entities.playbook import Playbook, PlaybookStep
from chimera.domain.services.playbook_engine import (
    PlaybookEngine,
    PlaybookExecutionStatus,
    StepStatus,
)


def _make_playbook(**overrides) -> Playbook:
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


def _mock_process(returncode: int = 0, stdout: bytes = b"ok", stderr: bytes = b""):
    """Create a mock async process."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


class TestPlaybookEngine:
    """Tests for PlaybookEngine execution service."""

    @pytest.fixture
    def engine(self):
        return PlaybookEngine()

    @pytest.mark.asyncio
    async def test_execute_valid_single_step(self, engine):
        """A single valid step should succeed."""
        playbook = _make_playbook()
        proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.SUCCEEDED
        assert len(result.step_results) == 1
        assert result.step_results[0].status == StepStatus.SUCCEEDED
        assert result.succeeded_steps == 1
        assert result.failed_steps == 0

    @pytest.mark.asyncio
    async def test_execute_multiple_steps_all_succeed(self, engine):
        """Multiple valid steps should all succeed."""
        playbook = _make_playbook(
            steps=(
                PlaybookStep(name="step1", command="systemctl restart a"),
                PlaybookStep(name="step2", command="nixos-rebuild switch"),
                PlaybookStep(name="step3", command="systemctl is-active a"),
            )
        )
        proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.SUCCEEDED
        assert result.succeeded_steps == 3
        assert result.failed_steps == 0

    @pytest.mark.asyncio
    async def test_execute_step_failure_without_rollback(self, engine):
        """A failing step with rollback_on_failure=False should fail without rollback."""
        playbook = _make_playbook(
            steps=(
                PlaybookStep(
                    name="fail",
                    command="systemctl restart foo",
                    rollback_on_failure=False,
                ),
            )
        )
        proc = _mock_process(returncode=1, stderr=b"service not found")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.FAILED
        assert result.step_results[0].status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_step_failure_triggers_rollback(self, engine):
        """A failing step with rollback_on_failure=True should roll back completed steps."""
        playbook = _make_playbook(
            steps=(
                PlaybookStep(
                    name="step1",
                    command="systemctl restart a",
                    rollback_on_failure=True,
                ),
                PlaybookStep(
                    name="step2-fails",
                    command="nixos-rebuild switch",
                    rollback_on_failure=True,
                ),
                PlaybookStep(
                    name="step3-skipped",
                    command="systemctl is-active a",
                ),
            )
        )

        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_process(returncode=0)
            return _mock_process(returncode=1, stderr=b"rebuild failed")

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.ROLLED_BACK
        assert result.step_results[0].status == StepStatus.ROLLED_BACK
        assert result.step_results[1].status == StepStatus.FAILED
        assert result.step_results[2].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_execute_rejects_invalid_playbook(self, engine):
        """A playbook that fails validation should not execute any steps."""
        playbook = _make_playbook(
            steps=(
                PlaybookStep(name="bad", command="rm -rf /"),
            )
        )

        result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.FAILED
        assert result.step_results[0].status == StepStatus.SKIPPED
        assert "validation failed" in result.step_results[0].error

    @pytest.mark.asyncio
    async def test_execute_rejects_disallowed_command_at_runtime(self, engine):
        """Even if validation is bypassed, command validation at step level catches bad commands."""
        # Directly test the internal _execute_step with a bad command
        step = PlaybookStep(name="bad", command="curl http://evil.com")
        step_result = await engine._execute_step(step)

        assert step_result.status == StepStatus.FAILED
        assert "not in allowlist" in step_result.error

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(self, engine):
        """Steps that exceed their timeout should fail."""
        playbook = _make_playbook(
            steps=(
                PlaybookStep(
                    name="slow",
                    command="systemctl restart foo",
                    timeout=1,
                    rollback_on_failure=False,
                ),
            )
        )

        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        proc.returncode = None

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            # We need wait_for to raise TimeoutError
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.FAILED
        assert result.step_results[0].status == StepStatus.FAILED
        assert "timed out" in result.step_results[0].error

    @pytest.mark.asyncio
    async def test_execute_records_timestamps(self, engine):
        """Execution should record start and completion timestamps."""
        playbook = _make_playbook()
        proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await engine.execute(playbook)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        assert result.step_results[0].started_at is not None
        assert result.step_results[0].completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_captures_output(self, engine):
        """Step output and errors should be captured."""
        playbook = _make_playbook()
        proc = _mock_process(returncode=0, stdout=b"service restarted", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await engine.execute(playbook)

        assert result.step_results[0].output == "service restarted"
        assert result.step_results[0].return_code == 0

    @pytest.mark.asyncio
    async def test_execute_empty_playbook_fails_validation(self, engine):
        """A playbook with no steps should fail validation."""
        playbook = _make_playbook(steps=())
        result = await engine.execute(playbook)

        assert result.status == PlaybookExecutionStatus.FAILED


class TestPlaybookEngineValidation:
    """Tests for PlaybookEngine command validation."""

    @pytest.fixture
    def engine(self):
        return PlaybookEngine()

    def test_validate_allowed_command(self, engine):
        parts = engine._validate_command("systemctl restart foo")
        assert parts == ["systemctl", "restart", "foo"]

    def test_validate_rejects_disallowed_command(self, engine):
        with pytest.raises(ValueError, match="not in allowlist"):
            engine._validate_command("rm -rf /")

    def test_validate_empty_command(self, engine):
        with pytest.raises(ValueError, match="Empty command"):
            engine._validate_command("")

    def test_validate_command_with_path(self, engine):
        parts = engine._validate_command("/usr/bin/systemctl restart foo")
        assert parts[0] == "/usr/bin/systemctl"
