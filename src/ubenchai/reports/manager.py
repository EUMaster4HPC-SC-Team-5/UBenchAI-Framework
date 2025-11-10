"""
ReportManager - central component to generate benchmark reports.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .models import ReportFormat, ReportJob, ReportJobStatus, ReportRecipe
from .recipe_loader import ReportRecipeLoader


class ReportManager:
    def __init__(
        self, recipe_directory: str = "recipes", output_root: str = "reports_output"
    ):
        self.recipe_loader = ReportRecipeLoader(recipe_directory=recipe_directory)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, ReportJob] = {}
        logger.info("ReportManager initialized")

    def list_available_reports(self) -> List[str]:
        return self.recipe_loader.list_available_recipes()

    def start_report(
        self, recipe_name: str, metadata: Optional[Dict] = None
    ) -> ReportJob:
        recipe = self.recipe_loader.load_recipe(recipe_name)
        job_id = str(uuid.uuid4())
        output_dir = self.output_root / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        job = ReportJob(
            id=job_id, recipe=recipe, output_dir=output_dir, metadata=metadata or {}
        )
        job.status = ReportJobStatus.RUNNING
        self._jobs[job_id] = job
        logger.info(f"Report job started: {job_id} ({recipe.name})")

        try:
            aggregated = self._aggregate_metrics(recipe, job)
            self._render_outputs(recipe, job, aggregated)
            job.status = ReportJobStatus.COMPLETED
        except Exception as exc:
            job.status = ReportJobStatus.FAILED
            logger.exception(f"Report job failed: {job_id} - {exc}")
        return job

    def get_job_status(self, job_id: str) -> Dict:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Report job not found: {job_id}")
        return job.to_dict()

    def list_jobs(self) -> List[Dict]:
        return [job.to_dict() for job in self._jobs.values()]

    def _aggregate_metrics(self, recipe: ReportRecipe, job: ReportJob) -> Dict:
        logger.info("Aggregating metrics for report")
        # Placeholder aggregation: read JSON/CSV files listed in metrics_sources
        aggregated: Dict[str, Dict] = {"sources": {}}
        for source in recipe.metrics_sources:
            src_type = (source.get("type") or "file").lower()
            name = source.get("name") or "unnamed"
            if src_type == "file":
                path = Path(source.get("path", "")).expanduser()
                if not path.exists():
                    logger.warning(f"Metrics source not found: {path}")
                    continue
                if path.suffix.lower() == ".json":
                    with open(path, "r") as f:
                        aggregated["sources"][name] = json.load(f)
                else:
                    # Minimal CSV support: keep raw text for now
                    aggregated["sources"][name] = {"raw_path": str(path)}
            else:
                logger.warning(f"Unsupported metrics source type: {src_type}")
        return aggregated

    def _render_outputs(
        self, recipe: ReportRecipe, job: ReportJob, aggregated: Dict
    ) -> None:
        for fmt in recipe.outputs:
            if fmt is ReportFormat.JSON:
                self._render_json(job, aggregated)
            elif fmt is ReportFormat.HTML:
                self._render_html(job, aggregated)
            elif fmt is ReportFormat.PDF:
                self._render_pdf_stub(job)

    def _render_json(self, job: ReportJob, data: Dict) -> Path:
        output = job.output_dir / "report.json"
        with open(output, "w") as f:
            json.dump({"job": job.to_dict(), "data": data}, f, indent=2)
        logger.info(f"Wrote JSON report: {output}")
        return output

    def _render_html(self, job: ReportJob, data: Dict) -> Path:
        output = job.output_dir / "report.html"

        # Use Jinja2 template for better HTML reports
        try:
            from jinja2 import Template

            template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .metric-card { transition: transform 0.2s; }
        .metric-card:hover { transform: translateY(-2px); }
        .chart-container { height: 300px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <span class="navbar-brand mb-0 h1">
                <i class="fas fa-chart-bar me-2"></i>UBenchAI Report
            </span>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row mb-4">
            <div class="col">
                <h1>{{ title }}</h1>
                <p class="text-muted">Generated on {{ timestamp }}</p>
            </div>
        </div>
        
        {% if data.sources %}
        <div class="row mb-4">
            <div class="col">
                <h3><i class="fas fa-database me-2"></i>Metrics Sources</h3>
                <div class="row">
                    {% for name, source in data.sources.items() %}
                    <div class="col-md-6 mb-3">
                        <div class="card metric-card">
                            <div class="card-header">
                                <h5>{{ name }}</h5>
                            </div>
                            <div class="card-body">
                                {% if source.cpu_percent is defined %}
                                <div class="row">
                                    <div class="col-6">
                                        <div class="text-center">
                                            <h4 class="text-primary">{{ source.cpu_percent }}%</h4>
                                            <small>CPU Usage</small>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <div class="text-center">
                                            <h4 class="text-success">{{ source.memory.percent }}%</h4>
                                            <small>Memory Usage</small>
                                        </div>
                                    </div>
                                </div>
                                {% else %}
                                <pre class="small">{{ source | tojson(indent=2) }}</pre>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="row">
            <div class="col">
                <h3><i class="fas fa-info-circle me-2"></i>Raw Data</h3>
                <div class="card">
                    <div class="card-body">
                        <pre class="small">{{ data | tojson(indent=2) }}</pre>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <footer class="bg-light mt-5 py-3">
        <div class="container text-center">
            <small class="text-muted">Generated by UBenchAI Framework v0.1.0</small>
        </div>
    </footer>
</body>
</html>
            """

            template = Template(template_str)
            html_content = template.render(
                title=f"UBenchAI Report - {job.recipe.name}",
                timestamp=str(job.created_at),
                data=data,
            )

        except ImportError:
            # Fallback to simple HTML if Jinja2 not available
            title = f"UBenchAI Report - {job.recipe.name}"
            body = (
                "<h1>"
                + title
                + "</h1>"
                + "<pre>"
                + json.dumps(data, indent=2)
                + "</pre>"
            )
            html_content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title></head><body>{body}</body></html>"""

        with open(output, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Wrote HTML report: {output}")
        return output

    def _render_pdf_stub(self, job: ReportJob) -> Path:
        """Generate PDF report using WeasyPrint"""
        output = job.output_dir / "report.pdf"

        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration

            # Create HTML content for PDF
            html_content = self._create_pdf_html(job)

            # CSS for PDF styling
            css_content = """
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: 'DejaVu Sans', sans-serif;
                font-size: 12px;
                line-height: 1.4;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }
            h2 {
                color: #34495e;
                margin-top: 20px;
            }
            .metric-box {
                border: 1px solid #bdc3c7;
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
            }
            .metric-value {
                font-size: 18px;
                font-weight: bold;
                color: #27ae60;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 10px 0;
            }
            th, td {
                border: 1px solid #bdc3c7;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #ecf0f1;
                font-weight: bold;
            }
            .footer {
                margin-top: 30px;
                text-align: center;
                font-size: 10px;
                color: #7f8c8d;
            }
            """

            # Generate PDF
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            css_doc = CSS(string=css_content, font_config=font_config)

            html_doc.write_pdf(output, stylesheets=[css_doc], font_config=font_config)
            logger.info(f"Wrote PDF report: {output}")
            return output

        except ImportError:
            # Fallback to text file if WeasyPrint not available
            output = job.output_dir / "report.pdf.txt"
            with open(output, "w", encoding="utf-8") as f:
                f.write(
                    "PDF generation requires WeasyPrint. Install with: pip install weasyprint\n"
                )
                f.write("For now, use HTML/JSON reports.\n")
            logger.info(f"Wrote PDF stub: {output}")
            return output
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            # Fallback to text file
            output = job.output_dir / "report.pdf.txt"
            with open(output, "w", encoding="utf-8") as f:
                f.write(f"PDF generation failed: {e}\n")
            return output

    def _create_pdf_html(self, job: ReportJob) -> str:
        """Create HTML content optimized for PDF generation"""
        # Get aggregated data
        aggregated = self._aggregate_metrics(job.recipe, job)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>UBenchAI Report - {job.recipe.name}</title>
        </head>
        <body>
            <h1>UBenchAI Benchmark Report</h1>
            <p><strong>Report:</strong> {job.recipe.name}</p>
            <p><strong>Generated:</strong> {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Job ID:</strong> {job.id}</p>
            
            <h2>Executive Summary</h2>
            <p>This report contains benchmark results and performance metrics collected by the UBenchAI Framework.</p>
            
            <h2>Metrics Overview</h2>
        """

        if aggregated.get("sources"):
            html += "<table>"
            html += "<tr><th>Source</th><th>Type</th><th>Status</th></tr>"
            for name, source in aggregated["sources"].items():
                source_type = (
                    "System Metrics" if "cpu_percent" in source else "Custom Data"
                )
                status = "Available" if source else "Missing"
                html += (
                    f"<tr><td>{name}</td><td>{source_type}</td><td>{status}</td></tr>"
                )
            html += "</table>"

        html += """
            <h2>Detailed Results</h2>
            <p>For detailed analysis, please refer to the JSON data or HTML report.</p>
            
            <div class="footer">
                <p>Generated by UBenchAI Framework v0.1.0</p>
                <p>EUMaster4HPC Student Challenge 2025-2026</p>
            </div>
        </body>
        </html>
        """

        return html
