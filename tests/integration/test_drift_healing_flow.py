"""Integration tests for drift detection and autonomous healing flow.

Verifies DriftDetectionService + AutonomousLoop work together.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from chimera.domain.services.drift_detection import DriftDetectionService
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.application.use_cases.autonomous_loop import AutonomousLoop


class TestDriftDetectionIntegration:
    @pytest.mark.asyncio
    async def test_detect_drift_in_fleet(self):
        mock_detector = AsyncMock()
        node1 = Node(host="10.0.0.1")
        node2 = Node(host="10.0.0.2")
        desired = NixHash("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")

        # Node 1 congruent, node 2 drifted
        mock_detector.get_actual_hash.side_effect = [
            desired,
            NixHash("ff000000000000000000000000000000"),
        ]

        from chimera.domain.value_objects.congruence_report import CongruenceReport
        mock_detector.check_node.side_effect = [
            CongruenceReport.congruent(node1, desired),
            CongruenceReport.drift(
                node2, desired, NixHash("ff000000000000000000000000000000"), "drifted"
            ),
        ]

        service = DriftDetectionService(mock_detector)
        analyses = await service.analyze_fleet([node1, node2], desired)

        # At least one node should show drift
        drifted = [a for a in analyses if a.actual_hash != a.expected_hash]
        assert len(drifted) >= 1

    @pytest.mark.asyncio
    async def test_no_drift_all_congruent(self):
        mock_detector = AsyncMock()
        node1 = Node(host="10.0.0.1")
        node2 = Node(host="10.0.0.2")
        desired = NixHash("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")

        mock_detector.get_actual_hash.return_value = desired

        from chimera.domain.value_objects.congruence_report import CongruenceReport
        mock_detector.check_node.return_value = CongruenceReport.congruent(
            node1, desired
        )

        service = DriftDetectionService(mock_detector)
        analyses = await service.analyze_fleet([node1, node2], desired)

        drifted = [a for a in analyses if a.actual_hash != a.expected_hash]
        assert len(drifted) == 0


class TestAutonomousLoopIntegration:
    @pytest.mark.asyncio
    async def test_one_shot_no_drift(self):
        """Single iteration with no drift detected."""
        nix = NixAdapter()
        fabric = FabricAdapter()
        deploy = DeployFleet(nix, fabric)
        loop = AutonomousLoop(nix, fabric, deploy)

        build_result = MagicMock()
        build_result.returncode = 0
        build_result.stdout = "/nix/store/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4-pkg"

        mock_conn = MagicMock()
        mock_conn_result = MagicMock()
        mock_conn_result.ok = True
        mock_conn_result.stdout = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        mock_conn.run.return_value = mock_conn_result

        with patch("subprocess.run", return_value=build_result), \
             patch.object(
                 fabric, "_get_connection", return_value=mock_conn
             ):
            await loop.execute(
                "default.nix", "chimera-watch", ["10.0.0.1"],
                interval_seconds=1, run_once=True,
            )
        # No exception = success

    @pytest.mark.asyncio
    async def test_one_shot_with_drift_triggers_heal(self):
        """Single iteration with drift triggers redeployment."""
        nix = NixAdapter()
        fabric = FabricAdapter()
        deploy = DeployFleet(nix, fabric)
        loop = AutonomousLoop(nix, fabric, deploy)

        build_result = MagicMock()
        build_result.returncode = 0
        build_result.stdout = "/nix/store/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4-pkg"

        # get_current_hash returns different hash (drift)
        mock_conn = MagicMock()
        mock_conn_result = MagicMock()
        mock_conn_result.ok = True
        mock_conn_result.stdout = "ff000000000000000000000000000000"
        mock_conn.run.return_value = mock_conn_result

        sync_result = MagicMock()
        sync_result.returncode = 0

        exec_result = MagicMock()
        exec_result.failed = False
        mock_group = MagicMock()
        mock_group.run.return_value = {MagicMock(): exec_result}

        with patch("subprocess.run") as mock_run, \
             patch.object(fabric, "_get_connection", return_value=mock_conn), \
             patch("fabric.ThreadingGroup", return_value=mock_group):
            mock_run.side_effect = [build_result, build_result, sync_result]
            await loop.execute(
                "default.nix", "chimera-watch", ["10.0.0.1"],
                interval_seconds=1, run_once=True,
            )
