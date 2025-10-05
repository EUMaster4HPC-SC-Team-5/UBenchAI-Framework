#!/usr/bin/env python3
"""
Command-line interface for UBenchAI Framework
"""

import sys
import argparse
from loguru import logger


def setup_logging(verbose: bool = False):
    """Configure logging for the application"""
    logger.remove()  # Remove default handler
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


def create_parser():
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        prog="ubenchai",
        description="Unified Benchmarking Framework for AI Factory Workloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ubenchai server start --recipe llm-inference
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
        # from ubenchai.servers.manager import ServerManager
        logger.info(f"Server Module - Action: {args.action}")
        # TODO: Initialize and run ServerManager based on args.action

    elif args.command == "client":
        # from ubenchai.clients.manager import ClientManager
        logger.info(f"Client Module - Action: {args.action}")
        # TODO: Initialize and run ClientManager based on args.action

    elif args.command == "monitor":
        # from ubenchai.monitors.manager import MonitorManager
        logger.info(f"Monitor Module - Action: {args.action}")
        # TODO: Initialize and run MonitorManager based on args.action


def print_usage():
    """Print usage information (kept for backward compatibility)"""
    parser = create_parser()
    parser.print_help()


if __name__ == "__main__":
    main()
