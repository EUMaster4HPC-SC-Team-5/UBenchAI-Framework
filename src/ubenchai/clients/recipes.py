"""
ClientRecipe and related specification classes
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml
from loguru import logger


# ============================================================================
# Specification Classes
# ============================================================================


@dataclass
class TargetSpec:
    """Target service specification"""

    service: Optional[str] = None  # Service name (e.g., "ollama-llm")
    endpoint: Optional[str] = None  # Direct endpoint (e.g., "http://mel2067:11434")
    protocol: str = "http"  # http, grpc, sql, s3
    timeout_seconds: int = 30

    def validate(self) -> bool:
        """Validate target specification"""
        if not self.service and not self.endpoint:
            raise ValueError("Either service or endpoint must be specified")
        if self.protocol not in ["http", "https", "grpc", "sql", "s3"]:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
        return True


@dataclass
class WorkloadSpec:
    """Workload pattern specification"""

    pattern: str = "closed-loop"  # open-loop, closed-loop
    duration_seconds: int = 60
    concurrent_users: int = 1
    requests_per_second: Optional[int] = None  # For open-loop
    think_time_ms: int = 0  # For closed-loop

    def validate(self) -> bool:
        """Validate workload specification"""
        if self.pattern not in ["open-loop", "closed-loop"]:
            raise ValueError(f"Unsupported pattern: {self.pattern}")
        if self.pattern == "open-loop" and self.requests_per_second is None:
            raise ValueError("requests_per_second required for open-loop pattern")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if self.concurrent_users <= 0:
            raise ValueError("concurrent_users must be positive")
        return True


@dataclass
class DatasetSpec:
    """Dataset specification"""

    type: str = "synthetic"  # synthetic, file, generator
    source: Optional[str] = None  # File path or generator name
    params: Dict = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate dataset specification"""
        if self.type not in ["synthetic", "file", "generator"]:
            raise ValueError(f"Unsupported dataset type: {self.type}")
        if self.type == "file" and not self.source:
            raise ValueError("source required for file dataset type")
        return True


@dataclass
class OrchestrationSpec:
    """Orchestration specification"""

    mode: str = "slurm"  # local, slurm, kubernetes
    resources: Dict = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate orchestration specification"""
        if self.mode not in ["local", "slurm", "kubernetes"]:
            raise ValueError(f"Unsupported orchestration mode: {self.mode}")
        return True


@dataclass
class OutputSpec:
    """Output specification"""

    metrics: List[str] = field(default_factory=lambda: ["latency", "throughput"])
    format: str = "json"  # json, csv, parquet
    destination: Optional[str] = None  # Output directory

    def validate(self) -> bool:
        """Validate output specification"""
        valid_metrics = [
            "latency",
            "throughput",
            "errors",
            "success_rate",
            "p50",
            "p95",
            "p99",
        ]
        for metric in self.metrics:
            if metric not in valid_metrics:
                raise ValueError(f"Unsupported metric: {metric}")
        if self.format not in ["json", "csv", "parquet"]:
            raise ValueError(f"Unsupported format: {self.format}")
        return True


# ============================================================================
# ClientRecipe
# ============================================================================


@dataclass
class ClientRecipe:
    """
    YAML-based configuration defining workload pattern (open/closed loop),
    dataset source, target endpoint, and orchestration parameters.
    """

    name: str
    target: TargetSpec
    workload: WorkloadSpec
    dataset: DatasetSpec = field(default_factory=DatasetSpec)
    orchestration: OrchestrationSpec = field(default_factory=OrchestrationSpec)
    output: OutputSpec = field(default_factory=OutputSpec)
    description: Optional[str] = None

    def validate(self) -> bool:
        """Validate the recipe configuration"""
        if not self.name:
            raise ValueError("Recipe name is required")

        # Validate all specs
        self.target.validate()
        self.workload.validate()
        self.dataset.validate()
        self.orchestration.validate()
        self.output.validate()

        logger.debug(f"Recipe validation passed for: {self.name}")
        return True

    def to_dict(self) -> Dict:
        """Convert recipe to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "target": {
                "service": self.target.service,
                "endpoint": self.target.endpoint,
                "protocol": self.target.protocol,
                "timeout_seconds": self.target.timeout_seconds,
            },
            "workload": {
                "pattern": self.workload.pattern,
                "duration_seconds": self.workload.duration_seconds,
                "concurrent_users": self.workload.concurrent_users,
                "requests_per_second": self.workload.requests_per_second,
                "think_time_ms": self.workload.think_time_ms,
            },
            "dataset": {
                "type": self.dataset.type,
                "source": self.dataset.source,
                "params": self.dataset.params,
            },
            "orchestration": {
                "mode": self.orchestration.mode,
                "resources": self.orchestration.resources,
            },
            "output": {
                "metrics": self.output.metrics,
                "format": self.output.format,
                "destination": self.output.destination,
            },
        }

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "ClientRecipe":
        """Load recipe from YAML file"""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Recipe file not found: {yaml_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        # Parse target
        target_data = data.get("target", {})
        target = TargetSpec(
            service=target_data.get("service"),
            endpoint=target_data.get("endpoint"),
            protocol=target_data.get("protocol", "http"),
            timeout_seconds=target_data.get("timeout_seconds", 30),
        )

        # Parse workload
        workload_data = data.get("workload", {})
        workload = WorkloadSpec(
            pattern=workload_data.get("pattern", "closed-loop"),
            duration_seconds=workload_data.get("duration_seconds", 60),
            concurrent_users=workload_data.get("concurrent_users", 1),
            requests_per_second=workload_data.get("requests_per_second"),
            think_time_ms=workload_data.get("think_time_ms", 0),
        )

        # Parse dataset
        dataset_data = data.get("dataset", {})
        dataset = DatasetSpec(
            type=dataset_data.get("type", "synthetic"),
            source=dataset_data.get("source"),
            params=dataset_data.get("params", {}),
        )

        # Parse orchestration
        orch_data = data.get("orchestration", {})
        orchestration = OrchestrationSpec(
            mode=orch_data.get("mode", "slurm"),
            resources=orch_data.get("resources", {}),
        )

        # Parse output
        output_data = data.get("output", {})
        output = OutputSpec(
            metrics=output_data.get("metrics", ["latency", "throughput"]),
            format=output_data.get("format", "json"),
            destination=output_data.get("destination"),
        )

        recipe = cls(
            name=data["name"],
            description=data.get("description"),
            target=target,
            workload=workload,
            dataset=dataset,
            orchestration=orchestration,
            output=output,
        )

        recipe.validate()
        logger.info(f"Loaded recipe: {recipe.name} from {yaml_path}")
        return recipe