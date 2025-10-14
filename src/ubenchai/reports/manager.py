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
    def __init__(self, recipe_directory: str = "recipes", output_root: str = "reports_output"):
        self.recipe_loader = ReportRecipeLoader(recipe_directory=recipe_directory)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, ReportJob] = {}
        logger.info("ReportManager initialized")

    def list_available_reports(self) -> List[str]:
        return self.recipe_loader.list_available_recipes()

    def start_report(self, recipe_name: str, metadata: Optional[Dict] = None) -> ReportJob:
        recipe = self.recipe_loader.load_recipe(recipe_name)
        job_id = str(uuid.uuid4())
        output_dir = self.output_root / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        job = ReportJob(id=job_id, recipe=recipe, output_dir=output_dir, metadata=metadata or {})
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

    def _render_outputs(self, recipe: ReportRecipe, job: ReportJob, aggregated: Dict) -> None:
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
        title = f"UBenchAI Report - {job.recipe.name}"
        body = "<h1>" + title + "</h1>" + "<pre>" + json.dumps(data, indent=2) + "</pre>"
        html = """<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>{}</title></head><body>{}</body></html>""".format(
            title, body
        )
        with open(output, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Wrote HTML report: {output}")
        return output

    def _render_pdf_stub(self, job: ReportJob) -> Path:
        output = job.output_dir / "report.pdf.txt"
        with open(output, "w", encoding="utf-8") as f:
            f.write("PDF generation not yet implemented. Use HTML/JSON.\n")
        logger.info(f"Wrote PDF stub: {output}")
        return output

