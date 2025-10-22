"""
Web Dashboard - Flask-based web interface for UBenchAI Framework
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from loguru import logger

from ..servers.manager import ServerManager
from ..servers.orchestrator import OrchestratorType
from ..monitors.manager import MonitorManager
from ..reports.manager import ReportManager
from ..health.checker import HealthChecker


class WebDashboard:
    """Web-based dashboard for UBenchAI Framework management"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        debug: bool = False,
        recipe_directory: str = "recipes",
        output_root: str = "logs",
    ):
        """
        Initialize the web dashboard

        Args:
            host: Host to bind the web server
            port: Port to bind the web server
            debug: Enable debug mode
            recipe_directory: Directory containing recipes
            output_root: Root directory for outputs
        """
        self.host = host
        self.port = port
        self.debug = debug

        # Initialize managers
        self.server_manager = ServerManager(
            orchestrator_type=OrchestratorType.SLURM, recipe_directory=recipe_directory
        )
        self.monitor_manager = MonitorManager(
            recipe_directory=recipe_directory, output_root=output_root
        )
        self.report_manager = ReportManager(
            recipe_directory=recipe_directory, output_root="reports_output"
        )
        self.health_checker = HealthChecker(output_dir=f"{output_root}/health")

        # Create Flask app
        self.app = self._create_app()

        logger.info(f"Web dashboard initialized on {host}:{port}")

    def _create_app(self) -> Flask:
        """Create and configure Flask application"""
        # Get the project root directory (2 levels up from this file)
        project_root = Path(__file__).resolve().parent.parent.parent
        templates_dir = project_root / "templates"

        logger.info(f"Looking for templates in: {templates_dir}")
        logger.info(f"Template directory exists: {templates_dir.exists()}")
        if templates_dir.exists():
            logger.info(f"Template files: {list(templates_dir.glob('*.html'))}")

        app = Flask(__name__, template_folder=str(templates_dir))
        app.secret_key = "ubenchai-dashboard-secret-key"

        # Register routes
        self._register_routes(app)

        return app

    def _register_routes(self, app: Flask) -> None:
        """Register all dashboard routes"""

        @app.route("/")
        def index():
            """Main dashboard page"""
            try:
                # Get overview statistics
                stats = {
                    "servers": {
                        "available": len(self.server_manager.list_available_services()),
                        "running": len(self.server_manager.list_running_services()),
                    },
                    "monitors": {
                        "available": len(self.monitor_manager.list_available_recipes()),
                        "running": len(self.monitor_manager.list_running_monitors()),
                    },
                    "reports": {
                        "available": len(self.report_manager.list_available_reports()),
                        "jobs": len(self.report_manager.list_jobs()),
                    },
                }

                # Get recent activity
                recent_services = self.server_manager.list_running_services()[:5]
                recent_monitors = self.monitor_manager.list_running_monitors()[:5]

                # Get system health
                health_summary = self.health_checker.get_health_summary()

                return render_template(
                    "dashboard.html",
                    stats=stats,
                    recent_services=recent_services,
                    recent_monitors=recent_monitors,
                    health_summary=health_summary,
                )
            except Exception as e:
                logger.error(f"Error loading dashboard: {e}")
                flash(f"Error loading dashboard: {e}", "error")
                try:
                    return render_template(
                        "dashboard.html",
                        stats={},
                        recent_services=[],
                        recent_monitors=[],
                        health_summary={},
                    )
                except Exception as template_error:
                    logger.error(f"Template rendering failed: {template_error}")
                    return f"""
                    <html>
                        <head><title>UBenchAI Dashboard</title></head>
                        <body>
                            <h1>UBenchAI Dashboard</h1>
                            <p>Error: {e}</p>
                            <p>Template Error: {template_error}</p>
                            <p>Please check that template files exist in the templates directory.</p>
                        </body>
                    </html>
                    """

        @app.route("/servers")
        def servers():
            """Server management page"""
            try:
                available_services = self.server_manager.list_available_services()
                running_services = self.server_manager.list_running_services()

                return render_template(
                    "servers.html",
                    available_services=available_services,
                    running_services=running_services,
                )
            except Exception as e:
                logger.error(f"Error loading servers: {e}")
                flash(f"Error loading servers: {e}", "error")
                return render_template(
                    "servers.html", available_services=[], running_services=[]
                )

        @app.route("/servers/start", methods=["POST"])
        def start_server():
            """Start a server from recipe"""
            try:
                recipe_name = request.form.get("recipe_name")
                if not recipe_name:
                    flash("Recipe name is required", "error")
                    return redirect(url_for("servers"))

                instance = self.server_manager.start_service(recipe_name)
                flash(f"Service started successfully: {instance.id}", "success")
                logger.info(f"Service started via web interface: {recipe_name}")

            except Exception as e:
                logger.error(f"Error starting service: {e}")
                flash(f"Error starting service: {e}", "error")

            return redirect(url_for("servers"))

        @app.route("/servers/stop/<service_id>", methods=["POST"])
        def stop_server(service_id):
            """Stop a server"""
            try:
                success = self.server_manager.stop_service(service_id)
                if success:
                    flash(f"Service stopped successfully: {service_id}", "success")
                else:
                    flash(f"Failed to stop service: {service_id}", "error")

            except Exception as e:
                logger.error(f"Error stopping service: {e}")
                flash(f"Error stopping service: {e}", "error")

            return redirect(url_for("servers"))

        @app.route("/servers/status/<service_id>")
        def server_status(service_id):
            """Get detailed server status"""
            try:
                status = self.server_manager.get_service_status(service_id)
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting service status: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route("/monitors")
        def monitors():
            """Monitor management page"""
            try:
                available_recipes = self.monitor_manager.list_available_recipes()
                running_monitors = self.monitor_manager.list_running_monitors()

                return render_template(
                    "monitors.html",
                    available_recipes=available_recipes,
                    running_monitors=running_monitors,
                )
            except Exception as e:
                logger.error(f"Error loading monitors: {e}")
                flash(f"Error loading monitors: {e}", "error")
                return render_template(
                    "monitors.html", available_recipes=[], running_monitors=[]
                )

        @app.route("/monitors/start", methods=["POST"])
        def start_monitor():
            """Start a monitor"""
            try:
                recipe_name = request.form.get("recipe_name")
                targets = request.form.get("targets", "")
                mode = request.form.get("mode", "local")

                if not recipe_name:
                    flash("Recipe name is required", "error")
                    return redirect(url_for("monitors"))

                target_list = (
                    [t.strip() for t in targets.split(",") if t.strip()]
                    if targets
                    else None
                )

                instance = self.monitor_manager.start_monitor(
                    recipe_name=recipe_name, targets=target_list, mode=mode
                )

                flash(f"Monitor started successfully: {instance.id}", "success")
                logger.info(f"Monitor started via web interface: {recipe_name}")

            except Exception as e:
                logger.error(f"Error starting monitor: {e}")
                flash(f"Error starting monitor: {e}", "error")

            return redirect(url_for("monitors"))

        @app.route("/monitors/stop/<monitor_id>", methods=["POST"])
        def stop_monitor(monitor_id):
            """Stop a monitor"""
            try:
                success = self.monitor_manager.stop_monitor(monitor_id)
                if success:
                    flash(f"Monitor stopped successfully: {monitor_id}", "success")
                else:
                    flash(f"Failed to stop monitor: {monitor_id}", "error")

            except Exception as e:
                logger.error(f"Error stopping monitor: {e}")
                flash(f"Error stopping monitor: {e}", "error")

            return redirect(url_for("monitors"))

        @app.route("/monitors/metrics/<monitor_id>")
        def monitor_metrics(monitor_id):
            """Get monitor metrics"""
            try:
                metrics_path = self.monitor_manager.export_metrics(monitor_id)
                with open(metrics_path, "r") as f:
                    metrics = json.load(f)
                return jsonify(metrics)
            except Exception as e:
                logger.error(f"Error getting monitor metrics: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route("/reports")
        def reports():
            """Report management page"""
            try:
                available_reports = self.report_manager.list_available_reports()
                report_jobs = self.report_manager.list_jobs()

                return render_template(
                    "reports.html",
                    available_reports=available_reports,
                    report_jobs=report_jobs,
                )
            except Exception as e:
                logger.error(f"Error loading reports: {e}")
                flash(f"Error loading reports: {e}", "error")
                return render_template(
                    "reports.html", available_reports=[], report_jobs=[]
                )

        @app.route("/reports/generate", methods=["POST"])
        def generate_report():
            """Generate a report"""
            try:
                recipe_name = request.form.get("recipe_name")
                if not recipe_name:
                    flash("Recipe name is required", "error")
                    return redirect(url_for("reports"))

                job = self.report_manager.start_report(recipe_name)
                flash(f"Report generation started: {job.id}", "success")
                logger.info(
                    f"Report generation started via web interface: {recipe_name}"
                )

            except Exception as e:
                logger.error(f"Error generating report: {e}")
                flash(f"Error generating report: {e}", "error")

            return redirect(url_for("reports"))

        @app.route("/reports/view/<job_id>")
        def view_report(job_id):
            """View a generated report"""
            try:
                job_status = self.report_manager.get_job_status(job_id)
                output_dir = Path(job_status["output_dir"])

                # Look for HTML report
                html_report = output_dir / "report.html"
                if html_report.exists():
                    return redirect(f"/static/reports/{job_id}/report.html")

                # Look for JSON report
                json_report = output_dir / "report.json"
                if json_report.exists():
                    with open(json_report, "r") as f:
                        report_data = json.load(f)
                    return render_template(
                        "report_view.html",
                        job_status=job_status,
                        report_data=report_data,
                    )

                flash("No report found", "error")
                return redirect(url_for("reports"))

            except Exception as e:
                logger.error(f"Error viewing report: {e}")
                flash(f"Error viewing report: {e}", "error")
                return redirect(url_for("reports"))

        @app.route("/api/health")
        def api_health():
            """API health check"""
            return jsonify(
                {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "version": "0.1.0",
                }
            )

        @app.route("/api/stats")
        def api_stats():
            """API for dashboard statistics"""
            try:
                stats = {
                    "servers": {
                        "available": len(self.server_manager.list_available_services()),
                        "running": len(self.server_manager.list_running_services()),
                    },
                    "monitors": {
                        "available": len(self.monitor_manager.list_available_recipes()),
                        "running": len(self.monitor_manager.list_running_monitors()),
                    },
                    "reports": {
                        "available": len(self.report_manager.list_available_reports()),
                        "jobs": len(self.report_manager.list_jobs()),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route("/api/health")
        def api_health_check():
            """API for system health check"""
            try:
                health_checks = self.health_checker.check_system_health()
                health_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "overall_status": health_checks["overall"].status.value,
                    "checks": {
                        name: check.to_dict() for name, check in health_checks.items()
                    },
                }
                return jsonify(health_data)
            except Exception as e:
                logger.error(f"Error performing health check: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route("/api/health/summary")
        def api_health_summary():
            """API for health summary"""
            try:
                summary = self.health_checker.get_health_summary()
                return jsonify(summary)
            except Exception as e:
                logger.error(f"Error getting health summary: {e}")
                return jsonify({"error": str(e)}), 500

    def run(self) -> None:
        """Run the web dashboard"""
        logger.info(f"Starting web dashboard on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=self.debug)


def create_app(
    host: str = "0.0.0.0",
    port: int = 5000,
    debug: bool = False,
    recipe_directory: str = "recipes",
    output_root: str = "logs",
) -> Flask:
    """
    Create and configure Flask application for UBenchAI Dashboard

    Args:
        host: Host to bind the web server
        port: Port to bind the web server
        debug: Enable debug mode
        recipe_directory: Directory containing recipes
        output_root: Root directory for outputs

    Returns:
        Configured Flask application
    """
    dashboard = WebDashboard(host, port, debug, recipe_directory, output_root)
    return dashboard.app
