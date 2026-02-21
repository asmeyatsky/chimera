"""
CLI Module

Architectural Intent:
- Command-line interface for Chimera
- Entry point for all user interactions
- Delegates to application use cases
"""

import argparse
import sys
import os
import asyncio
from pathlib import Path
from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
from chimera.application.use_cases.execute_local_deployment import (
    ExecuteLocalDeployment,
)
from chimera.application.use_cases.deploy_fleet import DeployFleet
from chimera.application.use_cases.rollback_deployment import RollbackDeployment
from chimera.application.use_cases.autonomous_loop import AutonomousLoop
from chimera.domain.value_objects.session_id import SessionId


async def async_main():
    parser = argparse.ArgumentParser(
        description="Project Chimera: The Autonomous Determinism Engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser(
        "run", help="Run a command in a persistent Nix+Tmux environment"
    )
    run_parser.add_argument(
        "--config", "-c", default="default.nix", help="Path to Nix config"
    )
    run_parser.add_argument(
        "--session", "-s", default="chimera-default", help="Tmux session name"
    )
    run_parser.add_argument("script_cmd", help="Command to run")

    attach_parser = subparsers.add_parser(
        "attach", help="Attach to a running Chimera session"
    )
    attach_parser.add_argument("session_id", help="Session ID to attach to")

    deploy_parser = subparsers.add_parser("deploy", help="Deploy to a fleet of nodes")
    deploy_parser.add_argument(
        "--targets", "-t", required=True, help="Comma-separated list of targets"
    )
    deploy_parser.add_argument(
        "--config", "-c", default="default.nix", help="Path to Nix config"
    )
    deploy_parser.add_argument(
        "--session", "-s", default="chimera-deploy", help="Remote session name"
    )
    deploy_parser.add_argument("script_cmd", help="Command to run remotely")

    watch_parser = subparsers.add_parser(
        "watch", help="Start Autonomous Drift Detection & Healing"
    )
    watch_parser.add_argument(
        "--targets", "-t", required=True, help="Comma-separated list of targets"
    )
    watch_parser.add_argument(
        "--config", "-c", default="default.nix", help="Path to Nix config"
    )
    watch_parser.add_argument(
        "--interval", "-i", type=int, default=10, help="Check interval in seconds"
    )
    watch_parser.add_argument("--once", action="store_true", help="Run once and exit")

    dash_parser = subparsers.add_parser("dash", help="Launch Chimera Fleet Dashboard")
    dash_parser.add_argument(
        "--targets", "-t", required=True, help="Comma-separated list of targets"
    )

    rollback_parser = subparsers.add_parser(
        "rollback", help="Time Machine: Rollback to previous generation"
    )
    rollback_parser.add_argument(
        "--targets", "-t", required=True, help="Comma-separated list of targets"
    )
    rollback_parser.add_argument(
        "--generation", "-g", help="Specific generation to switch to"
    )

    args = parser.parse_args()

    if args.command == "dash":
        from chimera.presentation.tui.dashboard import Dashboard

        targets = args.targets.split(",")
        app = Dashboard(targets)
        app.run()
        return

    if args.command == "rollback":
        fabric_adapter = FabricAdapter()
        use_case = RollbackDeployment(fabric_adapter)

        targets = args.targets.split(",")
        print(f"[*] Initiating Time Machine Rollback on {targets}...")
        success = await use_case.execute(targets, args.generation)
        if success:
            print("[+] Rollback Successful.")
        else:
            print("[-] Rollback Failed.")
            sys.exit(1)
        return

    if args.command == "watch":
        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()

        deploy_fleet = DeployFleet(nix_adapter, fabric_adapter, None)
        autonomous_loop = AutonomousLoop(nix_adapter, fabric_adapter, deploy_fleet)

        targets = args.targets.split(",")
        try:
            print(f"[*] Starting Chimera Autonomous Watch on {targets}...")
            await autonomous_loop.execute(
                args.config, args.session, targets, args.interval, args.once
            )
        except KeyboardInterrupt:
            print("\n[*] Stopping Autonomous Loop.")
            sys.exit(0)
        except Exception as e:
            print(f"[-] Autonomous Loop Failed: {e}")
            sys.exit(1)
        return

    if args.command == "run":
        nix_adapter = NixAdapter()
        tmux_adapter = TmuxAdapter()
        use_case = ExecuteLocalDeployment(nix_adapter, tmux_adapter)

        try:
            print(f"[*] Initializing Chimera Drift... Target: {args.session}")
            session_id = await use_case.execute(
                args.config, args.script_cmd, args.session
            )
            print(f"[+] Deployment Successful. Session '{session_id}' is active.")
            print(f"[*] To attach: chimera attach {session_id}")
        except Exception as e:
            print(f"[-] Deployment Failed: {e}")
            sys.exit(1)
        return

    if args.command == "deploy":
        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()

        use_case = DeployFleet(nix_adapter, fabric_adapter, None)

        targets = args.targets.split(",")
        try:
            print(f"[*] Deploying to fleet: {targets}...")
            success = await use_case.execute(
                args.config, args.script_cmd, args.session, targets
            )
            if success:
                print(f"[+] Deployment Successful to all nodes.")
            else:
                print(f"[-] Deployment Failed.")
                sys.exit(1)
        except Exception as e:
            print(f"[-] Deployment Failed: {e}")
            sys.exit(1)
        return

    if args.command == "attach":
        session_id = SessionId(args.session_id)
        tmux_adapter = TmuxAdapter()
        cmd = await tmux_adapter.attach_command(session_id)
        print(f"[*] Attaching to {session_id}...")

        cmd_parts = cmd.split()
        try:
            os.execvp(cmd_parts[0], cmd_parts)
        except FileNotFoundError:
            print("[-] Error: tmux not found.")
        return

    parser.print_help()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
