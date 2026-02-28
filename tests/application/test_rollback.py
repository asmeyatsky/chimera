"""Tests for RollbackDeployment use case."""

import pytest
from unittest.mock import AsyncMock
from chimera.application.use_cases.rollback_deployment import RollbackDeployment


class TestRollbackDeployment:
    @pytest.mark.asyncio
    async def test_successful_rollback(self):
        remote = AsyncMock()
        remote.rollback = AsyncMock(return_value=True)
        use_case = RollbackDeployment(remote)

        result = await use_case.execute(["10.0.0.1", "10.0.0.2"])

        assert result is True
        remote.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_with_generation(self):
        remote = AsyncMock()
        remote.rollback = AsyncMock(return_value=True)
        use_case = RollbackDeployment(remote)

        result = await use_case.execute(["10.0.0.1"], generation="42")

        assert result is True
        remote.rollback.assert_awaited_once()
        args, kwargs = remote.rollback.call_args
        # generation is passed as positional or keyword arg
        assert "42" in str(args) + str(kwargs)

    @pytest.mark.asyncio
    async def test_rollback_failure(self):
        remote = AsyncMock()
        remote.rollback = AsyncMock(return_value=False)
        use_case = RollbackDeployment(remote)

        result = await use_case.execute(["10.0.0.1"])

        assert result is False
