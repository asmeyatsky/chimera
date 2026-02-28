"""Tests for deployment DTOs."""

import pytest
from chimera.application.dtos.deployment_dtos import (
    DeployFleetRequest,
    DeployFleetResponse,
    RollbackRequest,
    RollbackResponse,
    LocalDeploymentRequest,
    LocalDeploymentResponse,
)


class TestDeployFleetRequest:
    def test_valid_request(self):
        req = DeployFleetRequest(
            config_path="default.nix",
            command="echo hi",
            session_name="test",
            targets=["10.0.0.1"],
        )
        assert req.config_path == "default.nix"

    def test_empty_config_rejected(self):
        with pytest.raises(ValueError, match="config_path"):
            DeployFleetRequest(
                config_path="", command="echo", session_name="s", targets=["x"]
            )

    def test_empty_command_rejected(self):
        with pytest.raises(ValueError, match="command"):
            DeployFleetRequest(
                config_path="x.nix", command="", session_name="s", targets=["x"]
            )

    def test_empty_session_rejected(self):
        with pytest.raises(ValueError, match="session_name"):
            DeployFleetRequest(
                config_path="x.nix", command="echo", session_name="", targets=["x"]
            )

    def test_empty_targets_rejected(self):
        with pytest.raises(ValueError, match="targets"):
            DeployFleetRequest(
                config_path="x.nix", command="echo", session_name="s", targets=[]
            )


class TestDeployFleetResponse:
    def test_success(self):
        resp = DeployFleetResponse(success=True, message="ok", nodes_deployed=3)
        assert resp.success
        assert resp.nodes_deployed == 3

    def test_failure(self):
        resp = DeployFleetResponse(success=False, message="fail")
        assert not resp.success
        assert resp.nodes_deployed == 0


class TestRollbackRequest:
    def test_valid(self):
        req = RollbackRequest(targets=["10.0.0.1"])
        assert req.generation is None

    def test_with_generation(self):
        req = RollbackRequest(targets=["10.0.0.1"], generation="42")
        assert req.generation == "42"

    def test_empty_targets_rejected(self):
        with pytest.raises(ValueError, match="targets"):
            RollbackRequest(targets=[])


class TestRollbackResponse:
    def test_response(self):
        resp = RollbackResponse(success=True, message="rolled back")
        assert resp.success


class TestLocalDeploymentRequest:
    def test_valid(self):
        req = LocalDeploymentRequest(
            config_path="x.nix", command="echo", session_name="s"
        )
        assert req.config_path == "x.nix"

    def test_empty_config_rejected(self):
        with pytest.raises(ValueError, match="config_path"):
            LocalDeploymentRequest(config_path="", command="echo", session_name="s")

    def test_empty_command_rejected(self):
        with pytest.raises(ValueError, match="command"):
            LocalDeploymentRequest(config_path="x.nix", command="", session_name="s")

    def test_empty_session_rejected(self):
        with pytest.raises(ValueError, match="session_name"):
            LocalDeploymentRequest(config_path="x.nix", command="echo", session_name="")


class TestLocalDeploymentResponse:
    def test_response(self):
        resp = LocalDeploymentResponse(success=True, session_id="s1", message="ok")
        assert resp.session_id == "s1"
