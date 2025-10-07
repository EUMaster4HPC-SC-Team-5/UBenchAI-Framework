"""
Complete services module with all service-related classes
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Lock
from datetime import datetime
import uuid
import yaml
from loguru import logger


# ============================================================================
# Enumerations
# ============================================================================


class ServiceStatus(Enum):
    """Service status enumeration"""

    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class Port:
    """Port mapping configuration"""

    container_port: int
    host_port: Optional[int] = None
    protocol: str = "tcp"


@dataclass
class VolumeMount:
    """Volume mount configuration"""

    host_path: str
    container_path: str
    readonly: bool = False


@dataclass
class ResourceSpec:
    """Resource requirements specification"""

    cpu_cores: int = 1
    memory_gb: int = 1
    gpu_count: int = 0
    gpu_type: Optional[str] = None
    disk_gb: int = 10
    network_bandwidth: Optional[int] = None

    def validate(self) -> bool:
        """Validate resource specifications"""
        if self.cpu_cores <= 0:
            raise ValueError("CPU cores must be positive")
        if self.memory_gb <= 0:
            raise ValueError("Memory must be positive")
        if self.gpu_count < 0:
            raise ValueError("GPU count cannot be negative")
        return True

    def to_slurm_resources(self) -> str:
        """Convert to SLURM resource string"""
        parts = [
            f"--cpus-per-task={self.cpu_cores}",
            f"--mem={self.memory_gb}G",
        ]
        if self.gpu_count > 0:
            gpu_str = f"--gres=gpu:{self.gpu_count}"
            if self.gpu_type:
                gpu_str = f"--gres=gpu:{self.gpu_type}:{self.gpu_count}"
            parts.append(gpu_str)
        return " ".join(parts)


@dataclass
class HealthCheck:
    """Health check configuration"""

    endpoint: str = "/health"
    interval_seconds: int = 10
    timeout_seconds: int = 5
    retries: int = 3
    initial_delay: int = 5


@dataclass
class Endpoint:
    """Service endpoint information"""

    url: str
    port: int
    protocol: str = "http"
    description: Optional[str] = None


# ============================================================================
# Service Recipe
# ============================================================================


@dataclass
class ServiceRecipe:
    """Service recipe configuration"""

    name: str
    image: str
    resources: ResourceSpec
    ports: List[Port] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[VolumeMount] = field(default_factory=list)
    healthcheck: Optional[HealthCheck] = None
    command: Optional[List[str]] = None
    working_dir: Optional[str] = None

    def validate(self) -> bool:
        """Validate the recipe configuration"""
        if not self.name:
            raise ValueError("Service name is required")
        if not self.image:
            raise ValueError("Container image is required")

        self.resources.validate()

        for port in self.ports:
            if port.container_port <= 0 or port.container_port > 65535:
                raise ValueError(f"Invalid port: {port.container_port}")

        logger.debug(f"Recipe validation passed for: {self.name}")
        return True

    def to_dict(self) -> Dict:
        """Convert recipe to dictionary"""
        return {
            "name": self.name,
            "image": self.image,
            "resources": {
                "cpu_cores": self.resources.cpu_cores,
                "memory_gb": self.resources.memory_gb,
                "gpu_count": self.resources.gpu_count,
                "gpu_type": self.resources.gpu_type,
            },
            "ports": [
                {
                    "container_port": p.container_port,
                    "host_port": p.host_port,
                    "protocol": p.protocol,
                }
                for p in self.ports
            ],
            "environment": self.environment,
            "volumes": [
                {
                    "host_path": v.host_path,
                    "container_path": v.container_path,
                    "readonly": v.readonly,
                }
                for v in self.volumes
            ],
        }

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "ServiceRecipe":
        """Load recipe from YAML file"""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Recipe file not found: {yaml_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        resources_data = data.get("resources", {})
        resources = ResourceSpec(
            cpu_cores=resources_data.get("cpu_cores", 1),
            memory_gb=resources_data.get("memory_gb", 1),
            gpu_count=resources_data.get("gpu_count", 0),
            gpu_type=resources_data.get("gpu_type"),
            disk_gb=resources_data.get("disk_gb", 10),
        )

        ports = [
            Port(
                container_port=p["container_port"],
                host_port=p.get("host_port"),
                protocol=p.get("protocol", "tcp"),
            )
            for p in data.get("ports", [])
        ]

        volumes = [
            VolumeMount(
                host_path=v["host_path"],
                container_path=v["container_path"],
                readonly=v.get("readonly", False),
            )
            for v in data.get("volumes", [])
        ]

        healthcheck = None
        if "healthcheck" in data:
            hc = data["healthcheck"]
            healthcheck = HealthCheck(
                endpoint=hc.get("endpoint", "/health"),
                interval_seconds=hc.get("interval_seconds", 10),
                timeout_seconds=hc.get("timeout_seconds", 5),
                retries=hc.get("retries", 3),
                initial_delay=hc.get("initial_delay", 5),
            )

        recipe = cls(
            name=data["name"],
            image=data["image"],
            resources=resources,
            ports=ports,
            environment=data.get("environment", {}),
            volumes=volumes,
            healthcheck=healthcheck,
            command=data.get("command"),
            working_dir=data.get("working_dir"),
        )

        recipe.validate()
        logger.info(f"Loaded recipe: {recipe.name} from {yaml_path}")
        return recipe


# ============================================================================
# Service Instance
# ============================================================================


@dataclass
class ServiceInstance:
    """Represents a running service instance with monitoring capabilities"""

    recipe: ServiceRecipe
    orchestrator_handle: str
    status: ServiceStatus = ServiceStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    endpoints: List[Endpoint] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation"""
        if not self.orchestrator_handle:
            raise ValueError("Orchestrator handle is required")
        if not self.recipe:
            raise ValueError("Service recipe is required")

        logger.debug(f"Created ServiceInstance: {self.id} for {self.recipe.name}")

    def update_status(self, new_status: ServiceStatus) -> None:
        """Update service status"""
        old_status = self.status
        self.status = new_status
        logger.info(
            f"Service {self.id} status: {old_status.value} -> {new_status.value}"
        )

    def add_endpoint(
        self,
        url: str,
        port: int,
        protocol: str = "http",
        description: Optional[str] = None,
    ) -> None:
        """Add an endpoint to the service"""
        endpoint = Endpoint(
            url=url, port=port, protocol=protocol, description=description
        )
        self.endpoints.append(endpoint)
        logger.debug(f"Added endpoint to service {self.id}: {url}:{port}")

    def get_logs(self) -> str:
        """Get service logs (placeholder - to be implemented with orchestrator)"""
        logger.debug(f"Fetching logs for service {self.id}")
        return f"Logs for service {self.id} not yet implemented"

    def get_metrics(self) -> Dict:
        """Get service metrics"""
        logger.debug(f"Fetching metrics for service {self.id}")
        return {
            "service_id": self.id,
            "status": self.status.value,
            "uptime_seconds": (datetime.now() - self.created_at).total_seconds(),
            "endpoints": len(self.endpoints),
        }

    def restart(self) -> bool:
        """Restart the service (placeholder)"""
        logger.info(f"Restarting service {self.id}")
        return False

    def scale(self, replicas: int) -> bool:
        """Scale the service (placeholder)"""
        logger.info(f"Scaling service {self.id} to {replicas} replicas")
        return False

    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self.status == ServiceStatus.RUNNING

    def to_dict(self) -> Dict:
        """Convert instance to dictionary representation"""
        return {
            "id": self.id,
            "recipe_name": self.recipe.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "orchestrator_handle": self.orchestrator_handle,
            "endpoints": [
                {
                    "url": e.url,
                    "port": e.port,
                    "protocol": e.protocol,
                    "description": e.description,
                }
                for e in self.endpoints
            ],
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ServiceInstance(id={self.id}, "
            f"recipe={self.recipe.name}, "
            f"status={self.status.value})"
        )


# ============================================================================
# Service Registry
# ============================================================================


class ServiceRegistry:
    """Registry that tracks all running service instances"""

    def __init__(self):
        """Initialize the service registry"""
        self._running_services: Dict[str, ServiceInstance] = {}
        self._service_lock = Lock()
        logger.info("ServiceRegistry initialized")

    def register_service(self, instance: ServiceInstance) -> bool:
        """Register a service instance"""
        with self._service_lock:
            if instance.id in self._running_services:
                logger.warning(f"Service {instance.id} already registered")
                return False

            self._running_services[instance.id] = instance
            logger.info(f"Registered service: {instance.id} ({instance.recipe.name})")
            return True

    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service instance"""
        with self._service_lock:
            if service_id not in self._running_services:
                logger.warning(f"Service {service_id} not found in registry")
                return False

            del self._running_services[service_id]
            logger.info(f"Unregistered service: {service_id}")
            return True

    def get_service(self, service_id: str) -> Optional[ServiceInstance]:
        """Get a service instance by ID"""
        with self._service_lock:
            return self._running_services.get(service_id)

    def get_all_services(self) -> List[ServiceInstance]:
        """Get all registered service instances"""
        with self._service_lock:
            return list(self._running_services.values())

    def get_services_by_status(self, status: ServiceStatus) -> List[ServiceInstance]:
        """Get services filtered by status"""
        with self._service_lock:
            return [
                svc for svc in self._running_services.values() if svc.status == status
            ]

    def cleanup_stale_services(self, max_age_hours: int = 24) -> int:
        """Clean up stale services that haven't been updated"""
        cleanup_count = 0
        now = datetime.now()

        with self._service_lock:
            stale_ids = []
            for service_id, instance in self._running_services.items():
                age_hours = (now - instance.created_at).total_seconds() / 3600

                if age_hours > max_age_hours and instance.status in [
                    ServiceStatus.STOPPED,
                    ServiceStatus.ERROR,
                    ServiceStatus.UNKNOWN,
                ]:
                    stale_ids.append(service_id)

            for service_id in stale_ids:
                del self._running_services[service_id]
                cleanup_count += 1
                logger.info(f"Cleaned up stale service: {service_id}")

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stale service(s)")

        return cleanup_count

    def get_service_count(self) -> int:
        """Get total number of registered services"""
        with self._service_lock:
            return len(self._running_services)

    def service_exists(self, service_id: str) -> bool:
        """Check if a service is registered"""
        with self._service_lock:
            return service_id in self._running_services

    def clear_all(self) -> int:
        """Clear all registered services (for testing/reset)"""
        with self._service_lock:
            count = len(self._running_services)
            self._running_services.clear()
            logger.warning(f"Cleared all {count} registered services")
            return count
