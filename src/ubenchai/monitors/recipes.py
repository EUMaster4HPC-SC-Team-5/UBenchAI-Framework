"""
Monitor Recipe and related specification classes
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml
from loguru import logger


@dataclass
class TargetService:
    """Target service to monitor"""

    name: str  # e.g., "vllm-llm", "ollama-llm"
    job_id: Optional[str] = None  # SLURM job ID
    endpoint: Optional[str] = None  # Direct endpoint if known
    metrics_path: str = "/metrics"  # Path to metrics endpoint
    port: int = 8000  # Default port

    def validate(self) -> bool:
        if not self.name and not self.endpoint:
            raise ValueError("Either name or endpoint must be specified")
        return True


@dataclass
class PrometheusConfig:
    """Prometheus component configuration"""

    enabled: bool = True
    image: str = "docker://prom/prometheus:latest"
    scrape_interval: str = "15s"
    retention_time: str = "24h"
    port: int = 9090
    partition: str = "cpu"
    resources: Dict = field(
        default_factory=lambda: {
            "cpu_cores": 2,
            "memory_gb": 4,
            "gpu_count": 0,
        }
    )

    def validate(self) -> bool:
        if self.port <= 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")
        return True


@dataclass
class GrafanaConfig:
    """Grafana component configuration"""

    enabled: bool = True
    image: str = "docker://grafana/grafana:latest"
    port: int = 3000
    partition: str = "cpu"
    admin_password: str = "admin"
    dashboards: List[str] = field(default_factory=list)
    resources: Dict = field(
        default_factory=lambda: {
            "cpu_cores": 2,
            "memory_gb": 4,
            "gpu_count": 0,
        }
    )

    def validate(self) -> bool:
        if self.port <= 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")
        return True


@dataclass
class ExporterConfig:
    """Node exporter configuration (optional)"""

    enabled: bool = False
    image: str = "docker://prom/node-exporter:latest"
    port: int = 9100
    resources: Dict = field(
        default_factory=lambda: {
            "cpu_cores": 1,
            "memory_gb": 1,
            "gpu_count": 0,
        }
    )


@dataclass
class MonitorRecipe:
    """
    Complete monitoring stack recipe
    Similar to ServiceRecipe but for monitoring components
    """

    name: str
    description: str
    targets: List[TargetService]
    prometheus: PrometheusConfig
    grafana: GrafanaConfig
    exporter: Optional[ExporterConfig] = None

    def validate(self) -> bool:
        """Validate the recipe configuration"""
        if not self.name:
            raise ValueError("Monitor name is required")

        if not self.targets:
            raise ValueError("At least one target service is required")

        for target in self.targets:
            target.validate()

        self.prometheus.validate()
        self.grafana.validate()

        if self.exporter:
            self.exporter.validate()

        logger.debug(f"Monitor recipe validation passed for: {self.name}")
        return True

    def to_dict(self) -> Dict:
        """Convert recipe to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "targets": [
                {
                    "name": t.name,
                    "job_id": t.job_id,
                    "endpoint": t.endpoint,
                    "metrics_path": t.metrics_path,
                    "port": t.port,
                }
                for t in self.targets
            ],
            "prometheus": {
                "enabled": self.prometheus.enabled,
                "image": self.prometheus.image,
                "scrape_interval": self.prometheus.scrape_interval,
                "retention_time": self.prometheus.retention_time,
                "port": self.prometheus.port,
                "resources": self.prometheus.resources,
            },
            "grafana": {
                "enabled": self.grafana.enabled,
                "image": self.grafana.image,
                "port": self.grafana.port,
                "dashboards": self.grafana.dashboards,
                "resources": self.grafana.resources,
            },
        }

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "MonitorRecipe":
        """Load monitor recipe from YAML file"""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Monitor recipe not found: {yaml_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        # Parse targets
        targets = []
        for t in data.get("targets", []):
            targets.append(
                TargetService(
                    name=t.get("name", ""),
                    job_id=t.get("job_id"),
                    endpoint=t.get("endpoint"),
                    metrics_path=t.get("metrics_path", "/metrics"),
                    port=t.get("port", 8000),
                )
            )

        # Parse Prometheus config
        prom_data = data.get("prometheus", {})
        prometheus = PrometheusConfig(
            enabled=prom_data.get("enabled", True),
            image=prom_data.get("image", "docker://prom/prometheus:latest"),
            scrape_interval=prom_data.get("scrape_interval", "15s"),
            retention_time=prom_data.get("retention_time", "24h"),
            port=prom_data.get("port", 9090),
            partition=prom_data.get("partition", "cpu"),
            resources=prom_data.get("resources", {}),
        )

        # Parse Grafana config
        graf_data = data.get("grafana", {})
        grafana = GrafanaConfig(
            enabled=graf_data.get("enabled", True),
            image=graf_data.get("image", "docker://grafana/grafana:latest"),
            port=graf_data.get("port", 3000),
            admin_password=graf_data.get("admin_password", "admin"),
            partition=graf_data.get("partition", "cpu"),
            dashboards=graf_data.get("dashboards", []),
            resources=graf_data.get("resources", {}),
        )

        # Parse exporter config (optional)
        exporter = None
        if "exporter" in data:
            exp_data = data["exporter"]
            exporter = ExporterConfig(
                enabled=exp_data.get("enabled", False),
                image=exp_data.get("image", "docker://prom/node-exporter:latest"),
                port=exp_data.get("port", 9100),
                resources=exp_data.get("resources", {}),
            )

        recipe = cls(
            name=data["name"],
            description=data.get("description", ""),
            targets=targets,
            prometheus=prometheus,
            grafana=grafana,
            exporter=exporter,
        )

        recipe.validate()
        logger.info(f"Loaded monitor recipe: {recipe.name} from {yaml_path}")
        return recipe
