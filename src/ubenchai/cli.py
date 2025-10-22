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
    logger.info(f"Client Module - Action: {args.action}")
    # TODO: Initialize and run ClientManager based on args.action


def handle_monitor_commands(args):
    """Handle monitor subcommands"""
    logger.info(f"Monitor Module - Action: {args.action}")
    from ubenchai.monitors.manager import MonitorManager

    manager = MonitorManager(recipe_directory="recipes", output_root="logs")

    if args.action == "start":
        targets = []
        if args.targets:
            targets = [t.strip() for t in args.targets.split(",") if t.strip()]
        inst = manager.start_monitor(args.recipe, targets=targets, mode=args.mode)
        print("\n Monitor started:")
        print(f"   Monitor ID: {inst.id}")
        print(f"   Recipe: {inst.recipe.name}")
        print(f"   Status: {inst.status}")
        if inst.grafana_url:
            print(f"   Grafana: {inst.grafana_url}")
        if inst.prometheus_url:
            print(f"   Prometheus: {inst.prometheus_url}")
    elif args.action == "stop":
        ok = manager.stop_monitor(args.monitor_id)
        if ok:
            print(f"\n Monitor stopped: {args.monitor_id}")
        else:
            print(f"\n Monitor not found: {args.monitor_id}")
    elif args.action == "list":
        print("\n Available Monitor Recipes:")
        recs = manager.list_available_recipes()
        if recs:
            for r in recs:
                print(f"   • {r}")
        else:
            print("   No monitor recipes found")

        print("\n Running Monitors:")
        mons = manager.list_running_monitors()
        if mons:
            table = []
            for m in mons:
                table.append(
                    [m["id"][:8], m["recipe"]["name"], m["status"], m["created_at"]]
                )
            print(
                tabulate(
                    table,
                    headers=["Monitor ID", "Recipe", "Status", "Created"],
                    tablefmt="simple",
                )
            )
        else:
            print("   No running monitors")
    elif args.action == "metrics":
        path = manager.export_metrics(args.monitor_id, output=args.output)
        print("\n Metrics exported:")
        print(f"   File: {path}")
    elif args.action == "report":
        # For now, just export metrics; users can run separate report command
        path = manager.export_metrics(args.monitor_id)
        print("\n Generated metrics snapshot for reporting:")
        print(f"   File: {path}")
    else:
        raise ValueError("Unknown monitor action")


def handle_report_commands(args):
    """Handle report subcommands"""
    from ubenchai.reports.manager import ReportManager

    manager = ReportManager(recipe_directory="recipes", output_root="reports_output")

    if args.action == "list":
        reports = manager.list_available_reports()
        print("\n Available Report Recipes:")
        if reports:
            for r in reports:
                print(f"   • {r}")
        else:
            print("   No report recipes found")
    elif args.action == "start":
        logger.info(f"Starting report from recipe: {args.recipe}")
        job = manager.start_report(args.recipe)
        print("\n Report started:")
        print(f"   Job ID: {job.id}")
        print(f"   Status: {job.status.value}")
        print(f"   Output: {job.output_dir}")
    elif args.action == "status":
        status = manager.get_job_status(args.job_id)
        print("\n Report Status:")
        print(f"   Job ID: {status['id']}")
        print(f"   Recipe: {status['recipe_name']}")
        print(f"   Status: {status['status']}")
        print(f"   Output Dir: {status['output_dir']}")
    else:
        raise ValueError("Unknown report action")


def handle_web_commands(args):
    """Handle web dashboard commands"""
    from ubenchai.web.dashboard import WebDashboard

    if args.action == "start":
        logger.info(f"Starting web dashboard on {args.host}:{args.port}")
        dashboard = WebDashboard(
            host=args.host,
            port=args.port,
            debug=args.debug,
            recipe_directory=args.recipe_directory,
            output_root=args.output_root,
        )

        print(f"\n Web Dashboard Starting...")
        print(f"   URL: http://{args.host}:{args.port}")
        print(f"   Recipe Directory: {args.recipe_directory}")
        print(f"   Output Root: {args.output_root}")
        print(f"   Debug Mode: {args.debug}")
        print(f"\n Press Ctrl+C to stop the dashboard")

        try:
            dashboard.run()
        except KeyboardInterrupt:
            print(f"\n Dashboard stopped by user")
            logger.info("Web dashboard stopped by user")
    else:
        raise ValueError("Unknown web action")


def handle_analysis_commands(args):
    """Handle analysis commands"""
    from ubenchai.analysis.analyzer import MetricsAnalyzer

    analyzer = MetricsAnalyzer()

    if args.action == "analyze":
        logger.info(f"Analyzing metrics file: {args.file}")
        summaries = analyzer.analyze_metrics_file(args.file)

        print(f"\n Metrics Analysis Results:")
        print(f"   File: {args.file}")
        print(f"   Metrics Found: {len(summaries)}")

        for name, summary in summaries.items():
            print(f"\n   {name}:")
            print(f"     Count: {summary.count}")
            print(f"     Mean: {summary.mean:.2f}")
            print(f"     Median: {summary.median:.2f}")
            print(f"     Min/Max: {summary.min_value:.2f} / {summary.max_value:.2f}")
            print(f"     Std Dev: {summary.std_dev:.2f}")

    elif args.action == "compare":
        logger.info(f"Comparing metrics: {args.baseline} vs {args.comparison}")
        results = analyzer.compare_metrics(args.baseline, args.comparison)

        print(f"\n Metrics Comparison Results:")
        print(f"   Baseline: {args.baseline}")
        print(f"   Comparison: {args.comparison}")
        print(f"   Metrics Compared: {len(results)}")

        for result in results:
            print(f"\n   {result.metric_name}:")
            print(f"     Baseline: {result.baseline_value:.2f}")
            print(f"     Comparison: {result.comparison_value:.2f}")
            print(f"     Change: {result.percent_change:+.1f}% ({result.significance})")

    elif args.action == "trends":
        logger.info(f"Analyzing trends across {len(args.files)} files")
        trends = analyzer.analyze_trends(args.files)

        print(f"\n Trend Analysis Results:")
        print(f"   Files Analyzed: {trends['files_analyzed']}")
        print(f"   Metrics with Trends: {len(trends['trends'])}")

        for metric_name, trend_data in trends["trends"].items():
            print(f"\n   {metric_name}:")
            print(f"     Trend: {trend_data['trend']}")
            print(f"     Volatility: {trend_data['volatility']:.2f}")
            print(
                f"     Range: {trend_data['min_value']:.2f} - {trend_data['max_value']:.2f}"
            )
            print(f"     Data Points: {trend_data['data_points']}")

    else:
        raise ValueError("Unknown analysis action")


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
    monitor_start.add_argument(
        "--mode",
        choices=["local", "slurm"],
        default="local",
        help="Run mode: local (default) or slurm",
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

    # Report subcommand (standalone reports from saved metrics)
    report_parser = subparsers.add_parser("report", help="Generate and manage reports")
    report_subparsers = report_parser.add_subparsers(
        dest="action", help="Report actions", required=True
    )

    # Report list
    report_subparsers.add_parser("list", help="List available report recipes")

    # Report start
    report_start = report_subparsers.add_parser(
        "start", help="Start a report generation job from a recipe"
    )
    report_start.add_argument(
        "--recipe", required=True, help="Name of the report recipe to run"
    )

    # Report status
    report_status = report_subparsers.add_parser(
        "status", help="Get status of a report job"
    )
    report_status.add_argument("job_id", help="Report job ID")

    # Web dashboard subcommand
    web_parser = subparsers.add_parser("web", help="Web dashboard interface")
    web_subparsers = web_parser.add_subparsers(
        dest="action", help="Web actions", required=True
    )

    # Web start
    web_start = web_subparsers.add_parser("start", help="Start the web dashboard")
    web_start.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the web server (default: 0.0.0.0)",
    )
    web_start.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind the web server (default: 5000)",
    )
    web_start.add_argument("--debug", action="store_true", help="Enable debug mode")
    web_start.add_argument(
        "--recipe-directory",
        default="recipes",
        help="Directory containing recipes (default: recipes)",
    )
    web_start.add_argument(
        "--output-root",
        default="logs",
        help="Root directory for outputs (default: logs)",
    )

    # Analysis subcommand
    analysis_parser = subparsers.add_parser(
        "analysis", help="Metrics analysis and comparison"
    )
    analysis_subparsers = analysis_parser.add_subparsers(
        dest="action", help="Analysis actions", required=True
    )

    # Analysis analyze
    analysis_analyze = analysis_subparsers.add_parser(
        "analyze", help="Analyze metrics from a file"
    )
    analysis_analyze.add_argument("file", help="Path to metrics JSON file")

    # Analysis compare
    analysis_compare = analysis_subparsers.add_parser(
        "compare", help="Compare metrics between two files"
    )
    analysis_compare.add_argument("baseline", help="Path to baseline metrics file")
    analysis_compare.add_argument("comparison", help="Path to comparison metrics file")

    # Analysis trends
    analysis_trends = analysis_subparsers.add_parser(
        "trends", help="Analyze trends across multiple files"
    )
    analysis_trends.add_argument("files", nargs="+", help="Paths to metrics files")

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
    elif args.command == "report":
        handle_report_commands(args)
    elif args.command == "web":
        handle_web_commands(args)
    elif args.command == "analysis":
        handle_analysis_commands(args)


if __name__ == "__main__":
    main()
