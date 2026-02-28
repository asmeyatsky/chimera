"""Tests for NixAdapter."""

import pytest
from unittest.mock import patch, MagicMock
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.domain.value_objects.nix_hash import NixHash


class TestNixAdapter:
    @pytest.mark.asyncio
    async def test_build_success(self):
        adapter = NixAdapter()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "/nix/store/abc12345abc12345abc12345abc12345-system"

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.build("default.nix")
            assert isinstance(result, NixHash)

    @pytest.mark.asyncio
    async def test_build_not_found(self):
        adapter = NixAdapter()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await adapter.build("default.nix")
            assert str(result) == "00000000000000000000000000000000"

    @pytest.mark.asyncio
    async def test_build_failure(self):
        adapter = NixAdapter()
        import subprocess
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "nix-build", stderr="error"),
        ):
            with pytest.raises(Exception, match="Nix build failed"):
                await adapter.build("default.nix")

    @pytest.mark.asyncio
    async def test_instantiate_success(self):
        adapter = NixAdapter()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "/nix/store/abc.drv"

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.instantiate("default.nix")
            assert result == "/nix/store/abc.drv"

    @pytest.mark.asyncio
    async def test_instantiate_not_found(self):
        adapter = NixAdapter()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await adapter.instantiate("default.nix")
            assert result == "default.nix.drv"

    @pytest.mark.asyncio
    async def test_shell(self):
        adapter = NixAdapter()
        result = await adapter.shell("default.nix", "echo hello")
        assert "nix-shell" in result
        assert "default.nix" in result
        assert "echo hello" in result
