"""
MonitorInstance, MonitorRegistry, and related classes
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from threading import Lock
import uuid
import json
from pathlib import Path
from loguru import logger

from ubenchai.monitors.recipes import MonitorRecipe


class MonitorStatus(Enum):
    """Monitor status enumeration"""

    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class MonitorComponent:
    """Individual component of the monitoring stack"""

    name: str  # "prometheus", "grafana", "node-exporter"
    job_id: str  # SLURM job ID
    endpoint: str  # Access URL
    status: MonitorStatus = MonitorStatus.PENDING


@dataclass
class MonitorInstance:
    """Represents a running monitoring stack instance"""

    recipe: MonitorRecipe
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    status: MonitorStatus = MonitorStatus.PENDING

    # Components
    components: Dict[str, MonitorComponent] = field(default_factory=dict)

    # Metadata
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation"""
        if not self.recipe:
            raise ValueError("Monitor recipe is required")

        logger.debug(f"Created MonitorInstance: {self.id} for {self.recipe.name}")

    def update_status(self, new_status: MonitorStatus) -> None:
        """Update monitor status"""
        old_status = self.status
        self.status = new_status
        logger.info(
            f"Monitor {self.id} status: {old_status.value} -> {new_status.value}"
        )

    def add_component(self, name: str, job_id: str, endpoint: str) -> None:
        """Add a component to the monitoring stack"""
        component = MonitorComponent(
            name=name,
            job_id=job_id,
            endpoint=endpoint,
        )
        self.components[name] = component
        logger.info(f"Added component {name} to monitor {self.id}: {endpoint}")

    def get_component(self, name: str) -> Optional[MonitorComponent]:
        """Get a component by name"""
        return self.components.get(name)

    @property
    def prometheus_url(self) -> Optional[str]:
        """Get Prometheus URL"""
        prom = self.get_component("prometheus")
        return prom.endpoint if prom else None

    @property
    def grafana_url(self) -> Optional[str]:
        """Get Grafana URL"""
        grafana = self.get_component("grafana")
        return grafana.endpoint if grafana else None

    def is_healthy(self) -> bool:
        """Check if monitor is healthy"""
        return self.status == MonitorStatus.RUNNING

    def to_dict(self) -> Dict:
        """Convert instance to dictionary representation"""
        return {
            "id": self.id,
            "recipe_name": self.recipe.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "components": {
                name: {
                    "job_id": comp.job_id,
                    "endpoint": comp.endpoint,
                    "status": comp.status.value,
                }
                for name, comp in self.components.items()
            },
            "prometheus_url": self.prometheus_url,
            "grafana_url": self.grafana_url,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"MonitorInstance(id={self.id}, "
            f"recipe={self.recipe.name}, "
            f"status={self.status.value})"
        )


class MonitorRegistry:
    """Registry that tracks all running monitor instances"""

    def __init__(self, state_file: str = "~/.ubenchai/monitor_instances.json"):
        """Initialize the monitor registry with persistent storage"""
        self._monitors: Dict[str, MonitorInstance] = {}
        self._monitor_lock = Lock()
        self.state_file = Path(state_file).expanduser()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"MonitorRegistry initialized with state file: {self.state_file}")

        # Load existing state
        self._load_state()

    def register(self, instance: MonitorInstance) -> bool:
        """Register a monitor instance"""
        with self._monitor_lock:
            if instance.id in self._monitors:
                logger.warning(f"Monitor {instance.id} already registered")
                return False

            self._monitors[instance.id] = instance
            self._save_state()
            logger.info(f"Registered monitor: {instance.id} ({instance.recipe.name})")
            return True

    def unregister(self, monitor_id: str) -> bool:
        """Unregister a monitor instance"""
        with self._monitor_lock:
            if monitor_id not in self._monitors:
                logger.warning(f"Monitor {monitor_id} not found in registry")
                return False

            del self._monitors[monitor_id]
            self._save_state()
            logger.info(f"Unregistered monitor: {monitor_id}")
            return True

    def get(self, monitor_id: str) -> Optional[MonitorInstance]:
        """Get a monitor by ID"""
        with self._monitor_lock:
            return self._monitors.get(monitor_id)

    def get_all(self) -> List[MonitorInstance]:
        """Get all registered monitors"""
        with self._monitor_lock:
            return list(self._monitors.values())

    def get_by_status(self, status: MonitorStatus) -> List[MonitorInstance]:
        """Get monitors filtered by status"""
        with self._monitor_lock:
            return [m for m in self._monitors.values() if m.status == status]

    def cleanup_stale(self, max_age_hours: int = 24) -> int:
        """Clean up stale monitors"""
        cleanup_count = 0
        now = datetime.now()

        with self._monitor_lock:
            stale_ids = []
            for monitor_id, instance in self._monitors.items():
                age_hours = (now - instance.created_at).total_seconds() / 3600

                if age_hours > max_age_hours and instance.status in [
                    MonitorStatus.STOPPED,
                    MonitorStatus.ERROR,
                    MonitorStatus.UNKNOWN,
                ]:
                    stale_ids.append(monitor_id)

            for monitor_id in stale_ids:
                del self._monitors[monitor_id]
                cleanup_count += 1
                logger.info(f"Cleaned up stale monitor: {monitor_id}")

            if cleanup_count > 0:
                self._save_state()

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stale monitor(s)")

        return cleanup_count

    def _save_state(self) -> None:
        """Save registry state to disk"""
        try:
            state = {
                monitor_id: instance.to_dict()
                for monitor_id, instance in self._monitors.items()
            }

            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2, default=str)

            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self) -> None:
        """Load registry state from disk"""
        if not self.state_file.exists():
            logger.debug("No existing state file found")
            return

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)

            # Note: Full restoration would require recipe reloading
            # For now, just log the count
            logger.info(f"Found {len(state)} monitor(s) in state file")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
