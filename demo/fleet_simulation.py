#!/usr/bin/env python3
"""
Chimera Fleet Simulation — 100-node multi-cloud demo

Provisions 100 nodes across AWS/GCP/Azure, injects drift on random nodes,
runs drift detection, autonomous healing, predictive analytics, and root
cause analysis. No real infrastructure required.
"""

import asyncio
import random
import sys
import time
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, ".")

from chimera.infrastructure.adapters.aws_adapter import AWSAdapter
from chimera.infrastructure.adapters.gcp_adapter import GCPAdapter
from chimera.infrastructure.adapters.azure_adapter import AzureAdapter
from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.domain.value_objects.congruence_report import CongruenceReport
from chimera.domain.services.drift_detection import (
    DriftDetectionService,
    DriftSeverity,
    HealingAction,
)
from chimera.domain.services.predictive_analytics import PredictiveAnalyticsService
from chimera.domain.services.root_cause_analysis import RootCauseAnalyzer
from chimera.infrastructure.agent.chimera_agent import (
    DriftReport,
    NodeHealth,
    AgentStatus,
    DriftSeverity as AgentDriftSeverity,
)


# ── Colours ──────────────────────────────────────────────────────────────
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

SEVERITY_COLOUR = {
    DriftSeverity.CRITICAL: RED,
    DriftSeverity.HIGH: YELLOW,
    DriftSeverity.MEDIUM: CYAN,
    DriftSeverity.LOW: GREEN,
}

ACTION_COLOUR = {
    HealingAction.ROLLBACK: RED,
    HealingAction.REBUILD: YELLOW,
    HealingAction.RESTART_SERVICE: CYAN,
    HealingAction.NONE: GREEN,
}


def bar(pct: float, width: int = 20) -> str:
    filled = int(pct * width)
    return f"[{'#' * filled}{'.' * (width - filled)}]"


# ── Mock drift detector that uses our injected state ─────────────────────
class SimulatedDriftDetector:
    """Implements DriftDetector protocol using in-memory drift state."""

    def __init__(self) -> None:
        self._drifted: dict[str, Optional[NixHash]] = {}

    def inject_drift(self, node: Node, actual: Optional[NixHash]) -> None:
        self._drifted[node.host] = actual

    def clear_drift(self, node: Node) -> None:
        self._drifted.pop(node.host, None)

    def clear_all(self) -> None:
        self._drifted.clear()

    async def check_node(self, node: Node, expected_hash: NixHash) -> CongruenceReport:
        if node.host in self._drifted:
            actual = self._drifted[node.host]
            return CongruenceReport.drift(
                node=node,
                expected=expected_hash,
                actual=actual,
                details=f"Hash mismatch on {node.host}",
            )
        return CongruenceReport.congruent(node=node, hash_val=expected_hash)

    async def get_actual_hash(self, node: Node) -> Optional[NixHash]:
        return self._drifted.get(node.host)


# ── Fleet metadata ───────────────────────────────────────────────────────
@dataclass
class FleetNode:
    node: Node
    provider: str
    name: str
    instance_type: str
    region: str


# ── Main simulation ──────────────────────────────────────────────────────
async def main() -> None:
    random.seed(42)

    # ─────────────────────────────────────────────────────────────────────
    # Phase 1: Provision 100 nodes across 3 clouds
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'=' * 72}")
    print(f"  CHIMERA FLEET SIMULATION — 100 Nodes, 3 Clouds, Full Autonomy")
    print(f"{'=' * 72}{RESET}\n")

    aws = AWSAdapter(region="us-east-1")
    gcp = GCPAdapter(project="chimera-prod", zone="us-central1-a")
    azure = AzureAdapter(resource_group="chimera-prod-rg", location="eastus")

    fleet: list[FleetNode] = []

    # AWS: 40 nodes across multiple instance types
    aws_types = [
        ("t3.micro", 10), ("t3.large", 10), ("m5.xlarge", 8),
        ("r5.2xlarge", 6), ("c5.4xlarge", 6),
    ]
    print(f"{BOLD}Provisioning AWS EC2 instances...{RESET}")
    idx = 0
    for itype, count in aws_types:
        for i in range(count):
            name = f"chimera-aws-{itype.replace('.', '-')}-{i:02d}"
            node = await aws.provision_node(name, instance_type=itype)
            fleet.append(FleetNode(node, "aws", name, itype, "us-east-1"))
            idx += 1
    print(f"  {GREEN}40 AWS nodes provisioned{RESET} (t3.micro/large, m5.xlarge, r5.2xlarge, c5.4xlarge)")

    # GCP: 35 nodes
    gcp_types = [
        ("e2-micro", 10), ("e2-medium", 8), ("n2-standard-4", 10),
        ("n2-standard-8", 7),
    ]
    print(f"{BOLD}Provisioning GCP Compute Engine instances...{RESET}")
    for mtype, count in gcp_types:
        for i in range(count):
            name = f"chimera-gcp-{mtype}-{i:02d}"
            node = await gcp.provision_node(name, instance_type=mtype)
            fleet.append(FleetNode(node, "gcp", name, mtype, "us-central1-a"))
    print(f"  {GREEN}35 GCP nodes provisioned{RESET} (e2-micro/medium, n2-standard-4/8)")

    # Azure: 25 nodes
    az_types = [
        ("Standard_B1s", 8), ("Standard_D4s_v3", 9), ("Standard_E2s_v3", 8),
    ]
    print(f"{BOLD}Provisioning Azure VMs...{RESET}")
    for vsize, count in az_types:
        for i in range(count):
            name = f"chimera-az-{vsize.lower().replace('_', '-')}-{i:02d}"
            node = await azure.provision_node(name, instance_type=vsize)
            fleet.append(FleetNode(node, "azure", name, vsize, "eastus"))
    print(f"  {GREEN}25 Azure VMs provisioned{RESET} (B1s, D4s_v3, E2s_v3)")

    all_nodes = [fn.node for fn in fleet]
    print(f"\n{BOLD}Fleet: {len(fleet)} nodes total{RESET}")
    for provider in ("aws", "gcp", "azure"):
        count = sum(1 for fn in fleet if fn.provider == provider)
        print(f"  {provider.upper():>6s}: {count} nodes")

    # ─────────────────────────────────────────────────────────────────────
    # Phase 2: Simulate autonomous healing loop (3 rounds)
    # ─────────────────────────────────────────────────────────────────────
    expected_hash = NixHash("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")
    detector = SimulatedDriftDetector()
    drift_service = DriftDetectionService(detector)
    analytics = PredictiveAnalyticsService(history_window_hours=168)
    rca = RootCauseAnalyzer()

    # node_id -> provider group mapping for RCA spatial correlation
    node_groups = {fn.node.host: fn.provider for fn in fleet}

    for round_num in range(1, 4):
        print(f"\n{BOLD}{'─' * 72}")
        print(f"  ROUND {round_num} — Autonomous Healing Cycle")
        print(f"{'─' * 72}{RESET}")

        # ── Inject drift on random nodes ────────────────────────────────
        detector.clear_all()

        # Scenario varies per round
        if round_num == 1:
            # Scattered drift: 12 random nodes, mixed severity
            drift_targets = random.sample(fleet, 12)
            for fn in drift_targets:
                if random.random() < 0.25:
                    detector.inject_drift(fn.node, None)  # CRITICAL
                elif random.random() < 0.5:
                    detector.inject_drift(fn.node, NixHash("00000000000000000000000000000000"))  # HIGH
                else:
                    detector.inject_drift(fn.node, NixHash("ffffffffffffffffffffffffffffffff"))  # MEDIUM
            scenario = "Scattered drift across providers (12 nodes)"

        elif round_num == 2:
            # Cloud-correlated: all AWS t3.large nodes drift simultaneously
            drift_targets = [fn for fn in fleet if fn.instance_type == "t3.large"]
            for fn in drift_targets:
                detector.inject_drift(fn.node, NixHash("deadbeefdeadbeefdeadbeefdeadbeef"))
            scenario = f"Correlated drift — all AWS t3.large nodes ({len(drift_targets)} nodes)"

        else:
            # Post-deploy wave: 20 nodes across all providers
            drift_targets = random.sample(fleet, 20)
            for fn in drift_targets:
                if random.random() < 0.15:
                    detector.inject_drift(fn.node, None)
                else:
                    detector.inject_drift(fn.node, NixHash("baadf00dbaadf00dbaadf00dbaadf00d"))
            scenario = "Post-deployment drift wave (20 nodes)"

        print(f"\n  {MAGENTA}Scenario:{RESET} {scenario}")
        time.sleep(0.3)

        # ── Fleet-wide drift analysis ───────────────────────────────────
        print(f"\n  {BOLD}Scanning fleet for drift...{RESET}")
        analyses = await drift_service.analyze_fleet(all_nodes, expected_hash)

        drifted = [a for a in analyses if a.needs_healing]
        congruent = [a for a in analyses if not a.needs_healing]

        pct_healthy = len(congruent) / len(fleet)
        colour = GREEN if pct_healthy > 0.9 else YELLOW if pct_healthy > 0.7 else RED
        print(f"\n  Fleet Health: {colour}{bar(pct_healthy)} {pct_healthy:.0%}{RESET}")
        print(f"  Congruent: {GREEN}{len(congruent)}{RESET}  Drifted: {RED}{len(drifted)}{RESET}")

        # ── Severity breakdown ──────────────────────────────────────────
        if drifted:
            print(f"\n  {BOLD}Drift Severity Breakdown:{RESET}")
            for sev in (DriftSeverity.CRITICAL, DriftSeverity.HIGH, DriftSeverity.MEDIUM, DriftSeverity.LOW):
                count = sum(1 for a in drifted if a.severity == sev)
                if count:
                    c = SEVERITY_COLOUR[sev]
                    print(f"    {c}{sev.name:10s}{RESET}  {count:3d} nodes")

            # ── Healing plan ────────────────────────────────────────────
            plan = drift_service.get_healing_plan(analyses)
            print(f"\n  {BOLD}Healing Plan:{RESET}")
            for action in (HealingAction.ROLLBACK, HealingAction.REBUILD, HealingAction.RESTART_SERVICE):
                nodes_for_action = plan[action]
                if nodes_for_action:
                    c = ACTION_COLOUR[action]
                    print(f"    {c}{action.name:18s}{RESET}  {len(nodes_for_action):3d} nodes")

            # ── Show affected nodes (first 8) ──────────────────────────
            print(f"\n  {BOLD}Affected Nodes (showing first 8):{RESET}")
            for a in drifted[:8]:
                fn = next(f for f in fleet if f.node == a.node)
                c = SEVERITY_COLOUR[a.severity]
                ac = ACTION_COLOUR[a.healing_action]
                actual_str = str(a.actual_hash)[:12] + "..." if a.actual_hash else "UNREACHABLE"
                print(
                    f"    {fn.provider.upper():>5s} {fn.name:40s} "
                    f"{c}{a.severity.name:10s}{RESET} "
                    f"{ac}{a.healing_action.name:18s}{RESET} "
                    f"{DIM}actual={actual_str}{RESET}"
                )
            if len(drifted) > 8:
                print(f"    {DIM}... and {len(drifted) - 8} more{RESET}")

            # ── Record drift for predictive analytics ───────────────────
            now = datetime.now(UTC)
            for a in drifted:
                analytics.record_drift(a.node, a.severity, now - timedelta(seconds=random.randint(0, 30)))

            # ── Simulate healing ────────────────────────────────────────
            print(f"\n  {BOLD}Executing autonomous healing...{RESET}")
            time.sleep(0.5)
            healed = 0
            failed = 0
            for a in drifted:
                if random.random() < 0.92:  # 92% success rate
                    detector.clear_drift(a.node)
                    analytics.record_resolution(a.node, random.uniform(2.0, 45.0))
                    healed += 1
                else:
                    failed += 1

            print(f"  Healed: {GREEN}{healed}{RESET}  Failed: {RED}{failed}{RESET}")

            # ── Root Cause Analysis ─────────────────────────────────────
            print(f"\n  {BOLD}Root Cause Analysis:{RESET}")
            drift_reports = [
                DriftReport(
                    node_id=a.node.host,
                    expected_hash=str(a.expected_hash),
                    actual_hash=str(a.actual_hash) if a.actual_hash else "none",
                    severity=AgentDriftSeverity[a.severity.name],
                    detected_at=now,
                )
                for a in drifted
            ]

            # Build health snapshots for drifted nodes
            health_snapshots = [
                NodeHealth(
                    node_id=a.node.host,
                    status=AgentStatus.DRIFT_DETECTED if a.actual_hash else AgentStatus.UNREACHABLE,
                    current_hash=str(a.actual_hash) if a.actual_hash else None,
                    expected_hash=str(a.expected_hash),
                )
                for a in drifted
            ]

            rca_report = rca.analyze(
                drift_reports=drift_reports,
                health_snapshots=health_snapshots,
                deploy_timestamps=[now - timedelta(seconds=20)] if round_num == 3 else None,
                node_groups={a.node.host: node_groups[a.node.host] for a in drifted},
            )

            cause_colour = {
                "LOCAL_ISSUE": CYAN,
                "UPSTREAM_CONFIG_CHANGE": YELLOW,
                "DEPLOY_RELATED": MAGENTA,
                "NETWORK_PARTITION": RED,
                "UNKNOWN": DIM,
            }
            cc = cause_colour.get(rca_report.probable_cause.name, "")
            conf_c = GREEN if rca_report.is_high_confidence else YELLOW
            print(f"    Probable Cause:  {cc}{rca_report.probable_cause.name}{RESET}")
            print(f"    Confidence:      {conf_c}{rca_report.confidence:.0%}{RESET}")
            print(f"    Affected Nodes:  {len(rca_report.affected_node_ids)}")
            print(f"    Causal Chain:")
            for step in rca_report.causal_chain.steps:
                # Truncate very long node lists for display
                display = step if len(step) < 80 else step[:77] + "..."
                print(f"      -> {display}")
            if rca_report.contributing_factors:
                print(f"    Signals ({len(rca_report.contributing_factors)}):")
                for f in rca_report.contributing_factors[:4]:
                    print(f"      - {f.description} {DIM}(weight={f.weight:.2f}){RESET}")

        # ── Post-healing verification ───────────────────────────────────
        print(f"\n  {BOLD}Post-healing verification...{RESET}")
        post_analyses = await drift_service.analyze_fleet(all_nodes, expected_hash)
        post_drifted = [a for a in post_analyses if a.needs_healing]
        post_healthy = len(fleet) - len(post_drifted)
        pct = post_healthy / len(fleet)
        colour = GREEN if pct > 0.95 else YELLOW
        print(f"  Fleet Health: {colour}{bar(pct)} {pct:.0%}{RESET} ({post_healthy}/{len(fleet)} congruent)")

    # ─────────────────────────────────────────────────────────────────────
    # Phase 3: Predictive Analytics Summary
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'=' * 72}")
    print(f"  PREDICTIVE ANALYTICS — Fleet Risk Assessment")
    print(f"{'=' * 72}{RESET}\n")

    risk_summary = analytics.fleet_risk_summary(all_nodes)
    print(f"  {BOLD}Fleet Risk Distribution:{RESET}")
    risk_colours = {"CRITICAL": RED, "HIGH": YELLOW, "MEDIUM": CYAN, "LOW": GREEN}
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        count = risk_summary[level]
        c = risk_colours[level]
        pct = count / len(fleet)
        print(f"    {c}{level:10s}{RESET}  {count:3d} nodes  {bar(pct, 30)} {pct:.0%}")

    # Top 10 riskiest nodes
    risk_scores = analytics.assess_fleet(all_nodes)
    high_risk = [s for s in risk_scores if s.is_high_risk]
    print(f"\n  {BOLD}Top 10 Highest-Risk Nodes:{RESET}")
    print(f"  {'Node':42s} {'Provider':>8s} {'Score':>6s} {'Level':>9s} {'P(drift)':>9s} {'Freq':>5s} {'Rec':>5s} {'Sev':>5s}")
    print(f"  {'─' * 42} {'─' * 8} {'─' * 6} {'─' * 9} {'─' * 9} {'─' * 5} {'─' * 5} {'─' * 5}")
    for score in risk_scores[:10]:
        fn = next(f for f in fleet if f.node == score.node)
        c = risk_colours.get(score.level.name, "")
        print(
            f"  {fn.name:42s} {fn.provider.upper():>8s} "
            f"{c}{score.score:6.3f}{RESET} "
            f"{c}{score.level.name:>9s}{RESET} "
            f"{score.predicted_drift_probability:8.1%}  "
            f"{score.factors.get('frequency', 0):5.2f} "
            f"{score.factors.get('recency', 0):5.2f} "
            f"{score.factors.get('severity', 0):5.2f}"
        )

    # MTTR for nodes that were healed
    nodes_with_mttr = [(fn, analytics.mean_time_to_resolution(fn.node))
                       for fn in fleet
                       if analytics.mean_time_to_resolution(fn.node) is not None]
    if nodes_with_mttr:
        avg_mttr = sum(m for _, m in nodes_with_mttr) / len(nodes_with_mttr)
        print(f"\n  {BOLD}Mean Time to Resolution (MTTR):{RESET}")
        print(f"    Fleet average: {GREEN}{avg_mttr:.1f}s{RESET}")
        print(f"    Nodes with resolution data: {len(nodes_with_mttr)}/{len(fleet)}")

    # Trending up?
    trending = [(fn, analytics.is_trending_up(fn.node)) for fn in fleet]
    trending_up = [fn for fn, t in trending if t]
    if trending_up:
        print(f"\n  {YELLOW}Trending Up (increasing drift frequency):{RESET}")
        for fn in trending_up[:5]:
            print(f"    {fn.name} ({fn.provider.upper()})")

    # ─────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'=' * 72}")
    print(f"  SIMULATION COMPLETE")
    print(f"{'=' * 72}{RESET}")
    print(f"  Nodes managed:       {len(fleet)}")
    print(f"  Clouds:              AWS ({sum(1 for f in fleet if f.provider == 'aws')}), "
          f"GCP ({sum(1 for f in fleet if f.provider == 'gcp')}), "
          f"Azure ({sum(1 for f in fleet if f.provider == 'azure')})")
    print(f"  Healing rounds:      3")
    print(f"  Drift events total:  {len(analytics._history)}")
    print(f"  High-risk nodes:     {len(high_risk)}")
    if nodes_with_mttr:
        print(f"  Avg MTTR:            {avg_mttr:.1f}s")
    print()


if __name__ == "__main__":
    asyncio.run(main())
