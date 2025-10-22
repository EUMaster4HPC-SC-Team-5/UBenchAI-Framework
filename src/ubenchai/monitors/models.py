"""
Monitor models for representing monitor recipes, instances, and statuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MonitorStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class MonitorRecipe:
    name: str
    description: str = ""
    target_services: List[str] = field(default_factory=list)
    collection_interval_seconds: int = 5
    retention_period_hours: int = 24
    exporters: List[Dict[str, Any]] = field(default_factory=list)
    grafana: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_yaml(file_path: str) -> "MonitorRecipe":
        import yaml

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        name = data.get("name")
        if not name:
            raise ValueError("Monitor recipe missing required field 'name'")

        return MonitorRecipe(
            name=name,
            description=data.get("description", ""),
            target_services=(data.get("target_services") or [])[:],
            collection_interval_seconds=int(data.get("collection_interval_seconds", 5)),
            retention_period_hours=int(data.get("retention_period_hours", 24)),
            exporters=data.get("exporters") or [],
            grafana=data.get("grafana") or {},
        )

    def validate(self) -> None:
        if self.collection_interval_seconds <= 0:
            raise ValueError("collection_interval_seconds must be > 0")
        if self.retention_period_hours <= 0:
            raise ValueError("retention_period_hours must be > 0")


@dataclass
class MonitorInstance:
    id: str
    recipe: MonitorRecipe
    status: MonitorStatus = MonitorStatus.STARTING
    created_at_iso: str = ""
    prometheus_url: Optional[str] = None
    grafana_url: Optional[str] = None
    targets: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "recipe": {
                "name": self.recipe.name,
                "description": self.recipe.description,
            },
            "status": self.status,
            "created_at": self.created_at_iso,
            "prometheus_url": self.prometheus_url,
            "grafana_url": self.grafana_url,
            "targets": list(self.targets),
            "metadata": dict(self.metadata),
        }



