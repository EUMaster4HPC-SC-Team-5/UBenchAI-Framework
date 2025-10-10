#!/usr/bin/env python3
"""
Command-line interface for UBenchAI Framework - Updated with ServerManager
"""

import sys
import argparse
from loguru import logger
from tabulate import tabulate


def setup_logging(verbose: bool = False):
    """Configure logging for the application"""
    logger.remove()
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level,
    )


def print_banner():
    """Print application banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║         UBenchAI Framework v0.1.0                     ║
    ║    Unified Benchmarking for AI Factory Workloads      ║
    ╚═══════════════════════════════════════════════════════╝
    """
    print(banner)


def handle_server_commands(args):
    """Handle server subcommands"""
    from ubenchai.servers.manager import ServerManager
    from ubenchai.servers.orchestrator import OrchestratorType

    # Initialize ServerManager
    manager = ServerManager(
        orchestrator_type=OrchestratorType.SLURM, recipe_directory="recipes"
    )

    try:
        if args.action == "start":
            # Start a service
            logger.info(f"Starting service from recipe: {args.recipe}")
            instance = manager.start_service(args.recipe)

            print(f"\n Service started successfully!")
            print(f"   Service ID: {instance.id}")
            print(f"   Recipe: {instance.recipe.name}")
            print(f"   Status: {instance.status.value}")
            print(f"   Orchestrator Handle: {instance.orchestrator_handle}")

        elif args.action == "stop":
            # Stop a service
            logger.info(f"Stopping service: {args.service_id}")
            success = manager.stop_service(args.service_id)

            if success:
                print(f"\n Service stopped successfully: {args.service_id}")
            else:
                print(f"\n Failed to stop service: {args.service_id}")
                sys.exit(1)

        elif args.action == "list":
            # List services
            print("\n Available Recipes:")
            recipes = manager.list_available_services()
            if recipes:
                for recipe in recipes:
                    info = manager.get_recipe_info(recipe)
                    print(f"   • {recipe}: {info.get('description', 'No description')}")
            else:
                print("   No recipes found")

            print("\n Running Services:")
            services = manager.list_running_services()
            if services:
                table_data = []
                for svc in services:
                    table_data.append(
                        [
                            svc["id"][:8],
                            svc["recipe_name"],
                            svc["status"],
                            svc["created_at"][:19],
                        ]
                    )
                print(
                    tabulate(
                        table_data,
                        headers=["Service ID", "Recipe", "Status", "Created At"],
                        tablefmt="simple",
                    )
                )
            else:
                print("   No running services")

        elif args.action == "status":
            # Get service status
            logger.info(f"Getting status for service: {args.service_id}")
            status = manager.get_service_status(args.service_id)

            print(f"\n Service Status:")
            print(f"   Service ID: {status['id']}")
            print(f"   Recipe: {status['recipe_name']}")
            print(f"   Status: {status['status']}")
            print(f"   Created: {status['created_at']}")
            print(f"   Orchestrator Handle: {status['orchestrator_handle']}")

            if status["endpoints"]:
                print(f"\n   Endpoints:")
                for ep in status["endpoints"]:
                    print(f"      • {ep['protocol']}://{ep['url']}:{ep['port']}")

    except FileNotFoundError as e:
        print(f"\n Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n Validation Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n Runtime Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n Unexpected Error: {e}")
        sys.exit(1)


def handle_client_commands(args):
    """Handle client subcommands"""
    from ubenchai.clients.manager import ClientManager
    
    manager = ClientManager(recipe_directory="recipes/clients")
    
    try:
        if args.action == "run":
            logger.info(f"Starting client from recipe: {args.recipe}")
            run = manager.start_client(args.recipe)
            
            print(f"\n✓ Client started successfully!")
            print(f"   Run ID: {run.id}")
            print(f"   Recipe: {run.recipe_name}")
            print(f"   Status: {run.status.value}")
            print(f"   Target: {run.target_endpoint}")
            print(f"   Orchestrator Handle: {run.orchestrator_handle}")
            
        elif args.action == "stop":
            logger.info(f"Stopping client run: {args.run_id}")
            success = manager.stop_client(args.run_id)
            
            if success:
                print(f"\n✓ Client run stopped: {args.run_id}")
            else:
                print(f"\n✗ Failed to stop run: {args.run_id}")
                sys.exit(1)
                
        elif args.action == "list":
            print("\n📋 Available Recipes:")
            recipes = manager.list_available_clients()
            if recipes:
                for recipe in recipes:
                    info = manager.get_recipe_info(recipe)
                    print(f"   • {recipe}: {info.get('description', 'No description')}")
            else:
                print("   No recipes found")
            
            print("\n🏃 Running Clients:")
            runs = manager.list_running_clients()
            if runs:
                table_data = []
                for r in runs:
                    table_data.append([
                        r['id'][:8],
                        r['recipe_name'],
                        r['status'],
                        r['created_at'][:19]
                    ])
                print(tabulate(
                    table_data,
                    headers=["Run ID", "Recipe", "Status", "Created At"],
                    tablefmt="simple"
                ))
            else:
                print("   No running clients")
                
        elif args.action == "status":
            logger.info(f"Getting status for run: {args.run_id}")
            status = manager.get_client_status(args.run_id)
            
            print(f"\n📊 Client Run Status:")
            print(f"   Run ID: {status['id']}")
            print(f"   Recipe: {status['recipe_name']}")
            print(f"   Status: {status['status']}")
            print(f"   Created: {status['created_at']}")
            print(f"   Target: {status['target_endpoint']}")
            print(f"   Orchestrator Handle: {status['orchestrator_handle']}")
            
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n✗ Validation Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n✗ Runtime Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n✗ Unexpected Error: {e}")
        sys.exit(1)


def handle_monitor_commands(args):
    """Handle monitor subcommands"""
    logger.info(f"Monitor Module - Action: {args.action}")
    # TODO: Initialize and run MonitorManager based on args.action


def create_parser():
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        prog="ubenchai",
        description="Unified Benchmarking Framework for AI Factory Workloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ubenchai server start --recipe ollama-llm
  ubenchai server list
  ubenchai server status <service-id>
  ubenchai server stop <service-id>

  ubenchai client run --recipe stress-test
  ubenchai monitor start --targets service1,service2

For more information, visit:
  https://github.com/EUMaster4HPC-SC-Team-5/UBenchAI-Framework
        """,
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose (DEBUG) logging"
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    # Server subcommand
    server_parser = subparsers.add_parser(
        "server", help="Manage containerized AI services"
    )
    server_subparsers = server_parser.add_subparsers(
        dest="action", help="Server actions", required=True
    )

    # Server start
    server_start = server_subparsers.add_parser(
        "start", help="Start a service from a recipe"
    )
    server_start.add_argument(
        "--recipe", required=True, help="Name of the service recipe to start"
    )
    server_start.add_argument("--config", help="Path to configuration override file")

    # Server stop
    server_stop = server_subparsers.add_parser("stop", help="Stop a running service")
    server_stop.add_argument("service_id", help="ID of the service to stop")

    # Server list
    server_subparsers.add_parser("list", help="List available or running services")

    # Server status
    server_status = server_subparsers.add_parser(
        "status", help="Get status of a service"
    )
    server_status.add_argument("service_id", help="ID of the service")

    # Client subcommand
    client_parser = subparsers.add_parser("client", help="Run benchmarking workloads")
    client_subparsers = client_parser.add_subparsers(
        dest="action", help="Client actions", required=True
    )

    # Client run
    client_run = client_subparsers.add_parser(
        "run", help="Run a client workload from a recipe"
    )
    client_run.add_argument(
        "--recipe", required=True, help="Name of the client recipe to run"
    )
    client_run.add_argument("--overrides", help="Path to configuration overrides file")

    # Client stop
    client_stop = client_subparsers.add_parser("stop", help="Stop a running client")
    client_stop.add_argument("run_id", help="ID of the client run to stop")

    # Client list
    client_subparsers.add_parser(
        "list", help="List available client recipes or running clients"
    )

    # Client status
    client_status = client_subparsers.add_parser(
        "status", help="Get status of a client run"
    )
    client_status.add_argument("run_id", help="ID of the client run")

    # Monitor subcommand
    monitor_parser = subparsers.add_parser(
        "monitor", help="Start monitoring and metrics collection"
    )
    monitor_subparsers = monitor_parser.add_subparsers(
        dest="action", help="Monitor actions", required=True
    )

    # Monitor start
    monitor_start = monitor_subparsers.add_parser(
        "start", help="Start a monitoring session from a recipe"
    )
    monitor_start.add_argument(
        "--recipe", required=True, help="Name of the monitor recipe to start"
    )
    monitor_start.add_argument(
        "--targets", help="Comma-separated list of target services to monitor"
    )

    # Monitor stop
    monitor_stop = monitor_subparsers.add_parser(
        "stop", help="Stop a monitoring session"
    )
    monitor_stop.add_argument("monitor_id", help="ID of the monitor to stop")

    # Monitor list
    monitor_subparsers.add_parser(
        "list", help="List available monitor recipes or running monitors"
    )

    # Monitor metrics
    monitor_metrics = monitor_subparsers.add_parser(
        "metrics", help="Show metrics from a monitoring session"
    )
    monitor_metrics.add_argument("monitor_id", help="ID of the monitor")
    monitor_metrics.add_argument("--output", help="Output file for metrics (optional)")

    # Monitor report
    monitor_report = monitor_subparsers.add_parser(
        "report", help="Generate a report from monitoring data"
    )
    monitor_report.add_argument("monitor_id", help="ID of the monitor")
    monitor_report.add_argument(
        "--format",
        choices=["html", "json", "pdf"],
        default="html",
        help="Report format (default: html)",
    )

    return parser


def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    print_banner()

    logger.info("UBenchAI Framework starting...")

    # Route to appropriate module based on command
    if args.command == "server":
        handle_server_commands(args)
    elif args.command == "client":
        handle_client_commands(args)
    elif args.command == "monitor":
        handle_monitor_commands(args)


if __name__ == "__main__":
    main()
