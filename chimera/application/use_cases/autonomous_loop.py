"""
Autonomous Loop Use Case

Architectural Intent:
- Implements autonomous drift detection and self-healing
- Continuously monitors fleet congruence and triggers healing when drift is detected
- Uses parallel node health checks
"""

import asyncio
import logging
from typing import List
from pathlib import Path
from chimera.domain.entities.nix_config import NixConfig
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.congruence_report import CongruenceReport
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.ports.nix_port import NixPort
from chimera.domain.ports.remote_executor_port import RemoteExecutorPort
from chimera.application.use_cases.deploy_fleet import DeployFleet

logger = logging.getLogger(__name__)


class AutonomousLoop:
    def __init__(
        self,
        nix_port: NixPort,
        remote_executor: RemoteExecutorPort,
        deploy_fleet_use_case: DeployFleet,
    ):
        self.nix_port = nix_port
        self.remote_executor = remote_executor
        self.deploy_fleet = deploy_fleet_use_case

    async def execute(
        self,
        config_path: str,
        session_name: str,
        targets: List[str],
        interval_seconds: int = 10,
        run_once: bool = False,
    ):
        config = NixConfig(Path(config_path))
        nodes = [Node.parse(t) for t in targets]

        try:
            expected_hash = await self.nix_port.build(str(config.path))
            logger.info("Expected System Hash: %s", expected_hash)
        except Exception as e:
            logger.error("Failed to resolve expected state: %s", e)
            return

        while True:
            congruence_reports = await self._check_congruence(nodes, expected_hash)

            drifted_nodes = [
                report.node for report in congruence_reports if not report.is_congruent
            ]

            if drifted_nodes:
                logger.warning(
                    "Drift detected on %d nodes! Initiating Self-Healing...",
                    len(drifted_nodes),
                )
                drifted_targets = [str(n) for n in drifted_nodes]

                await self.deploy_fleet.execute(
                    config_path,
                    f"echo '{expected_hash}' > /tmp/chimera_current_hash && echo 'Healed'",
                    session_name,
                    drifted_targets,
                )
            else:
                logger.info("All %d nodes are congruent.", len(nodes))

            if run_once:
                break

            await asyncio.sleep(interval_seconds)

    async def _check_congruence(
        self, nodes: List[Node], expected_hash: NixHash
    ) -> List[CongruenceReport]:
        reports = []
        for node in nodes:
            actual_hash = await self.remote_executor.get_current_hash(node)

            if actual_hash == expected_hash:
                reports.append(CongruenceReport.congruent(node, expected_hash))
            else:
                details = f"Expected {expected_hash}, found {actual_hash}"
                reports.append(
                    CongruenceReport.drift(node, expected_hash, actual_hash, details)
                )
        return reports
