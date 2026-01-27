import argparse
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from chimera.infrastructure.adapters.nix_adapter import NixAdapter
from chimera.infrastructure.adapters.tmux_adapter import TmuxAdapter
from chimera.application.use_cases.execute_local_deployment import ExecuteLocalDeployment
from chimera.domain.value_objects.session_id import SessionId

def main():
    parser = argparse.ArgumentParser(description="Project Chimera: The Autonomous Determinism Engine")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run Command
    run_parser = subparsers.add_parser("run", help="Run a command in a persistent Nix+Tmux environment")
    run_parser.add_argument("--config", "-c", default="default.nix", help="Path to Nix config (default.nix or flake.nix)")
    run_parser.add_argument("--session", "-s", default="chimera-default", help="Tmux session name")
    run_parser.add_argument("script_cmd", help="Command to run (e.g., 'python3 script.py')")

    # Attach Command
    attach_parser = subparsers.add_parser("attach", help="Attach to a running Chimera session")
    attach_parser.add_argument("session_id", help="Session ID to attach to")

    # Deploy Command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy to a fleet of nodes")
    deploy_parser.add_argument("--targets", "-t", required=True, help="Comma-separated list of targets (user@host:port)")
    deploy_parser.add_argument("--config", "-c", default="default.nix", help="Path to Nix config")
    deploy_parser.add_argument("--session", "-s", default="chimera-deploy", help="Remote session name")
    deploy_parser.add_argument("script_cmd", help="Command to run remotely")

    # Watch Command (Autonomous)
    watch_parser = subparsers.add_parser("watch", help="Start Autonomous Drift Detection & Healing")
    watch_parser.add_argument("--targets", "-t", required=True, help="Comma-separated list of targets")
    watch_parser.add_argument("--config", "-c", default="default.nix", help="Path to Nix config")
    watch_parser.add_argument("--interval", "-i", type=int, default=10, help="Check interval in seconds")
    watch_parser.add_argument("--once", action="store_true", help="Run congruence check once and exit")
    watch_parser.add_argument("--session", "-s", default="chimera-auto", help="Session name for healing")

    args = parser.parse_args()

    # ... (existing handlers)

    if args.command == "watch":
        from chimera.application.use_cases.autonomous_loop import AutonomousLoop
        from chimera.application.use_cases.deploy_fleet import DeployFleet
        from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
        
        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()
        
        deploy_fleet = DeployFleet(nix_adapter, fabric_adapter, None)
        autonomous_loop = AutonomousLoop(nix_adapter, fabric_adapter, deploy_fleet)
        
        targets = args.targets.split(",")
        try:
            print(f"[*] Starting Chimera Autonomous Watch on {targets}...")
            autonomous_loop.execute(args.config, args.session, targets, args.interval, args.once)
        except KeyboardInterrupt:
            print("\n[*] Stopping Autonomous Loop.")
            sys.exit(0)
        except Exception as e:
            print(f"[-] Autonomous Loop Failed: {e}")
            sys.exit(1)

    elif args.command == "run":
        nix_adapter = NixAdapter()
        tmux_adapter = TmuxAdapter()
        use_case = ExecuteLocalDeployment(nix_adapter, tmux_adapter)
        
        try:
            print(f"[*] Initializing Chimera Drift... Target: {args.session}")
            session_id = use_case.execute(args.config, args.script_cmd, args.session)
            print(f"[+] Deployment Successful. Session '{session_id}' is active.")
            print(f"[*] To attach: chimera attach {session_id}")
            
        except Exception as e:
            print(f"[-] Deployment Failed: {e}")
            sys.exit(1)

    elif args.command == "deploy":
        from chimera.application.use_cases.deploy_fleet import DeployFleet
        from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter
        
        nix_adapter = NixAdapter()
        fabric_adapter = FabricAdapter()
        
        use_case = DeployFleet(nix_adapter, fabric_adapter, None)
        
        targets = args.targets.split(",")
        try:
            print(f"[*] Deploying to fleet: {targets}...")
            result = use_case.execute(args.config, args.script_cmd, args.session, targets)
            if result:
                print(f"[+] Deployment Successful to all nodes.")
            else:
                print(f"[-] Deployment Failed.")
                sys.exit(1)
        except Exception as e:
             print(f"[-] Deployment Failed: {e}")
             sys.exit(1)

    elif args.command == "attach":
        session_id = SessionId(args.session_id)
        tmux_adapter = TmuxAdapter()
        # We need to run the attach command in the current terminal. 
        # Python script cannot easily replace itself with tmux attach in the shell provided, 
        # but we can try os.execvp or just print the command.
        # "chimera attach" implies the tool itself does the attaching.
        cmd = tmux_adapter.attach_command(session_id)
        print(f"[*] Attaching to {session_id}...")
        
        # Execute tmux attach
        cmd_parts = cmd.split()
        try:
            os.execvp(cmd_parts[0], cmd_parts)
        except FileNotFoundError:
             print("[-] Error: tmux not found.")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
