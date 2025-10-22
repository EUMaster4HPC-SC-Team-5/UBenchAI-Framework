"""
ClientRun, RunRegistry, and related classes for tracking benchmark runs
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from threading import Lock
from pathlib import Path
import uuid
import json
from loguru import logger


# ============================================================================
# Enumerations
# ============================================================================


class RunStatus(Enum):
    """Benchmark run status enumeration"""

    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


# ============================================================================
# ClientRun
# ============================================================================


@dataclass
class ClientRun:
    """
    Represents a single benchmarking run.
    Stores recipe, run status, timestamps, orchestrator handle, and output artifacts.
    """

    recipe_name: str
    orchestrator_handle: str
    status: RunStatus = RunStatus.SUBMITTED
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    artifacts_dir: Optional[str] = None
    target_endpoint: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation"""

    if not self.recipe_name:
        raise ValueError("Recipe name is required")

    logger.debug(f"Created ClientRun: {self.id} for {self.recipe_name}")

    def update_status(self, new_status: RunStatus) -> None:
        """Update run status"""
        old_status = self.status
        self.status = new_status

        if new_status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED]:
            self.completed_at = datetime.now()

        logger.info(f"Run {self.id} status: {old_status.value} -> {new_status.value}")

    def get_duration(self) -> Optional[float]:
        """Get run duration in seconds"""
        if self.completed_at:
            return (self.completed_at - self.created_at).total_seconds()
        return (datetime.now() - self.created_at).total_seconds()

    def get_logs(self) -> str:
        """Get run logs (placeholder - to be implemented with orchestrator)"""
        logger.debug(f"Fetching logs for run {self.id}")
        return f"Logs for run {self.id} not yet implemented"

    def get_metrics(self) -> Dict:
        """Get run metrics"""
        logger.debug(f"Fetching metrics for run {self.id}")

        duration = self.get_duration()

        return {
            "run_id": self.id,
            "recipe_name": self.recipe_name,
            "status": self.status.value,
            "duration_seconds": duration,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "target_endpoint": self.target_endpoint,
        }

    def to_dict(self) -> Dict:
        """Convert run to dictionary representation"""
        return {
            "id": self.id,
            "recipe_name": self.recipe_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "orchestrator_handle": self.orchestrator_handle,
            "artifacts_dir": self.artifacts_dir,
            "target_endpoint": self.target_endpoint,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ClientRun":
        """Create ClientRun from dictionary"""
        return cls(
            id=data["id"],
            recipe_name=data["recipe_name"],
            status=RunStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            orchestrator_handle=data["orchestrator_handle"],
            artifacts_dir=data.get("artifacts_dir"),
            target_endpoint=data.get("target_endpoint"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ClientRun(id={self.id}, "
            f"recipe={self.recipe_name}, "
            f"status={self.status.value})"
        )


# ============================================================================
# RunRegistry
# ============================================================================


class RunRegistry:
    """
    Tracks active and historical client runs.
    Supports cleanup and ensures consistent metadata storage.

    IMPORTANT: This registry persists to disk to solve the state loss problem
    observed in the Server Module.
    """

    def __init__(self, state_file: str = "~/.ubenchai/client_runs.json"):
        """Initialize the run registry with persistent storage"""
        self._runs: Dict[str, ClientRun] = {}
        self._run_lock = Lock()
        self.state_file = Path(state_file).expanduser()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"RunRegistry initialized with state file: {self.state_file}")

        # Load existing state
        self._load_state()

    def register(self, run: ClientRun) -> bool:
        """Register a client run"""
        with self._run_lock:
            if run.id in self._runs:
                logger.warning(f"Run {run.id} already registered")
                return False

            self._runs[run.id] = run
            self._save_state()
            logger.info(f"Registered run: {run.id} ({run.recipe_name})")
            return True

    def unregister(self, run_id: str) -> bool:
        """Unregister a client run"""
        with self._run_lock:
            if run_id not in self._runs:
                logger.warning(f"Run {run_id} not found in registry")
                return False

            del self._runs[run_id]
            self._save_state()
            logger.info(f"Unregistered run: {run_id}")
            return True

    def get(self, run_id: str) -> Optional[ClientRun]:
        """Get a run by ID"""
        with self._run_lock:
            return self._runs.get(run_id)

    def get_all(self) -> List[ClientRun]:
        """Get all registered runs"""
        with self._run_lock:
            return list(self._runs.values())

    def get_runs_by_status(self, status: RunStatus) -> List[ClientRun]:
        """Get runs filtered by status"""
        with self._run_lock:
            return [run for run in self._runs.values() if run.status == status]

    def cleanup_stale_runs(self, max_age_hours: int = 24) -> int:
        """Clean up stale runs that haven't been updated"""
        cleanup_count = 0
        now = datetime.now()

        with self._run_lock:
            stale_ids = []
            for run_id, run in self._runs.items():
                age_hours = (now - run.created_at).total_seconds() / 3600

                if age_hours > max_age_hours and run.status in [
                    RunStatus.COMPLETED,
                    RunStatus.FAILED,
                    RunStatus.CANCELED,
                ]:
                    stale_ids.append(run_id)

            for run_id in stale_ids:
                del self._runs[run_id]
                cleanup_count += 1
                logger.info(f"Cleaned up stale run: {run_id}")

            if cleanup_count > 0:
                self._save_state()

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stale run(s)")

        return cleanup_count

    def get_run_count(self) -> int:
        """Get total number of registered runs"""
        with self._run_lock:
            return len(self._runs)

    def run_exists(self, run_id: str) -> bool:
        """Check if a run is registered"""
        with self._run_lock:
            return run_id in self._runs

    def clear_all(self) -> int:
        """Clear all registered runs (for testing/reset)"""
        with self._run_lock:
            count = len(self._runs)
            self._runs.clear()
            self._save_state()
            logger.warning(f"Cleared all {count} registered runs")
            return count

    # ========================================================================
    # Persistence Methods (Solution to Server Module's state loss problem)
    # ========================================================================

    def _save_state(self) -> None:
        """Save registry state to disk"""
        try:
            state = {run_id: run.to_dict() for run_id, run in self._runs.items()}

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

            for run_id, run_dict in state.items():
                try:
                    run = ClientRun.from_dict(run_dict)
                    self._runs[run_id] = run
                except Exception as e:
                    logger.error(f"Failed to restore run {run_id}: {e}")

            logger.info(f"Loaded {len(self._runs)} run(s) from state file")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
