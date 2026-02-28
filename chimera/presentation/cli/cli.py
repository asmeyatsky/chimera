"""
CLI Module

Architectural Intent:
- Command-line interface for Chimera
- Entry point for all user interactions
- Delegates to application use cases via composition root
- Supports --verbose/--debug flags for log level control
"""

import argparse
import sys
import os
import asyncio
import logging
import traceback
from pathlib import Path
from chimera.infrastructure.logging import configure_logging
from chimera.domain.value_objects.session_id import SessionId


async def async_main():
    parser = argparse.ArgumentParser(
        description="Project Chimera: The Autonomous Determinism Engine"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug output with tracebacks"
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

    mcp_parser = subparsers.add_parser(
        "mcp", help="Start MCP server for agentic interactions"
    )
    mcp_parser.add_argument(
        "--port", "-p", type=int, default=8765, help="MCP server port"
    )
    mcp_parser.add_argument("--host", default="localhost", help="MCP server host")

    args = parser.parse_args()

    # Configure logging based on flags
    if args.debug:
        configure_logging(level=logging.DEBUG)
    elif args.verbose:
        configure_logging(level=logging.INFO)
    else:
        configure_logging(level=logging.WARNING)

    verbose = args.verbose or args.debug

    if args.command == "mcp":
        from chimera.infrastructure.mcp_servers.chimera_server import (
            create_chimera_server,
        )
        from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
        from chimera.infrastructure.adapters.nix_adapter import NixAdapter
        from chimera.application.use_cases.deploy_fleet import DeployFleet
        from chimera.application.use_cases.rollback_deployment import RollbackDeployment

        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()
        deploy_fleet = DeployFleet(nix_adapter, fabric_adapter)
        rollback = RollbackDeployment(fabric_adapter)

        server = create_chimera_server(deploy_fleet, rollback)

        print(f"[*] Starting MCP server on {args.host}:{args.port}...")
        print("[*] MCP tools registered:")

        async def run_server():
            tools = await server.list_tools()
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            print("[*] MCP server running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)

        try:
            asyncio.run(run_server())
        except KeyboardInterrupt:
            print("\n[*] MCP server stopped.")
        return

    if args.command == "dash":
        from chimera.presentation.tui.dashboard import Dashboard

        targets = args.targets.split(",")
        app = Dashboard(targets)
        app.run()
        return

    if args.command == "rollback":
        from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
        from chimera.application.use_cases.rollback_deployment import RollbackDeployment

        fabric_adapter = FabricAdapter()
        use_case = RollbackDeployment(fabric_adapter)

        targets = args.targets.split(",")
        print(f"[*] Initiating Time Machine Rollback on {targets}...")
        try:
            success = await use_case.execute(targets, args.generation)
            if success:
                print("[+] Rollback Successful.")
            else:
                print("[-] Rollback Failed.")
                sys.exit(1)
        except ConnectionError as e:
            print(f"[-] Connection error: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        except Exception as e:
            print(f"[-] Rollback Failed: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        return

    if args.command == "watch":
        from chimera.infrastructure.adapters.nix_adapter import NixAdapter
        from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
        from chimera.application.use_cases.deploy_fleet import DeployFleet
        from chimera.application.use_cases.autonomous_loop import AutonomousLoop

        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()

        deploy_fleet = DeployFleet(nix_adapter, fabric_adapter)
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
        except FileNotFoundError as e:
            print(f"[-] Config file not found: {e}")
            sys.exit(1)
        except ConnectionError as e:
            print(f"[-] Connection error: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        except Exception as e:
            print(f"[-] Autonomous Loop Failed: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        return

    if args.command == "run":
        from chimera.infrastructure.adapters.nix_adapter import NixAdapter
        from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
        from chimera.application.use_cases.execute_local_deployment import (
            ExecuteLocalDeployment,
        )

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
        except FileNotFoundError as e:
            print(f"[-] Config file not found: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[-] Deployment Failed: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        return

    if args.command == "deploy":
        from chimera.infrastructure.adapters.nix_adapter import NixAdapter
        from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
        from chimera.application.use_cases.deploy_fleet import DeployFleet

        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()

        use_case = DeployFleet(nix_adapter, fabric_adapter)

        targets = args.targets.split(",")
        try:
            print(f"[*] Deploying to fleet: {targets}...")
            print("[*] Step 1/4: Building Nix derivation...")
            success = await use_case.execute(
                args.config, args.script_cmd, args.session, targets
            )
            if success:
                print("[+] Deployment Successful to all nodes.")
            else:
                print("[-] Deployment Failed.")
                sys.exit(1)
        except FileNotFoundError as e:
            print(f"[-] Config file not found: {e}")
            sys.exit(1)
        except ConnectionError as e:
            print(f"[-] Connection error: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        except Exception as e:
            print(f"[-] Deployment Failed: {e}")
            if verbose:
                traceback.print_exc()
            sys.exit(1)
        return

    if args.command == "attach":
        from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter

        session_id = SessionId(args.session_id)
        tmux_adapter = TmuxAdapter()
        cmd = await tmux_adapter.attach_command(session_id)
        print(f"[*] Attaching to {session_id}...")

        cmd_parts = cmd.split()
        try:
            os.execvp(cmd_parts[0], cmd_parts)
        except FileNotFoundError:
            print("[-] Error: tmux not found. Install tmux and try again.")
        return

    parser.print_help()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
