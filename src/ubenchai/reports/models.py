"""
Data models for the reporting module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReportFormat(str, Enum):
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


class ReportJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportRecipe:
    name: str
    description: str = ""
    metrics_sources: List[Dict[str, Any]] = field(default_factory=list)
    comparisons: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[ReportFormat] = field(default_factory=lambda: [ReportFormat.HTML])

    @staticmethod
    def from_yaml(file_path: str) -> "ReportRecipe":
        import yaml

        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}

        name = data.get("name")
        if not name:
            raise ValueError("Report recipe missing required field 'name'")

        outputs_raw = data.get("outputs", ["html"]) or ["html"]
        outputs: List[ReportFormat] = []
        for fmt in outputs_raw:
            try:
                outputs.append(ReportFormat(fmt))
            except Exception as exc:
                raise ValueError(f"Unsupported report format: {fmt}") from exc

        return ReportRecipe(
            name=name,
            description=data.get("description", ""),
            metrics_sources=data.get("metrics_sources", []) or [],
            comparisons=data.get("comparisons", []) or [],
            outputs=outputs,
        )

    def validate(self) -> None:
        if not self.metrics_sources:
            raise ValueError("Report recipe must define at least one metrics_sources entry")


@dataclass
class ReportJob:
    id: str
    recipe: ReportRecipe
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: ReportJobStatus = ReportJobStatus.PENDING
    output_dir: Path = field(default_factory=lambda: Path("reports_output"))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "recipe_name": self.recipe.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "output_dir": str(self.output_dir),
            "metadata": self.metadata,
        }

