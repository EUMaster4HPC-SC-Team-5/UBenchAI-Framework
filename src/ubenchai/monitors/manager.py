"""
MonitorManager - central component to start/stop and manage monitoring runs.
Implements local collection, file export, and stubs for Prometheus/Grafana/SLURM.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # Fallback if not installed; local collector will error politely

from .models import MonitorInstance, MonitorRecipe, MonitorStatus
from .recipe_loader import MonitorRecipeLoader


class MonitorManager:
    def __init__(self, recipe_directory: str = "recipes", output_root: str = "logs"):
        self.recipe_loader = MonitorRecipeLoader(recipe_directory=recipe_directory)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._instances: Dict[str, MonitorInstance] = {}
        logger.info("MonitorManager initialized")
        self._load_existing_instances()

    def list_available_recipes(self) -> List[str]:
        return self.recipe_loader.list_available_recipes()

    def list_running_monitors(self) -> List[Dict]:
        return [m.to_dict() for m in self._instances.values()]

    def start_monitor(
        self,
        recipe_name: str,
        targets: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        mode: str = "local",
    ) -> MonitorInstance:
        recipe = self.recipe_loader.load_recipe(recipe_name)
        monitor_id = str(uuid.uuid4())
        created_at_iso = datetime.utcnow().isoformat() + "Z"
        instance = MonitorInstance(
            id=monitor_id,
            recipe=recipe,
            status=MonitorStatus.STARTING,
            created_at_iso=created_at_iso,
            targets=targets or recipe.target_services,
            metadata=metadata or {},
        )
        self._instances[monitor_id] = instance
        logger.info(f"Monitor started: {monitor_id} ({recipe.name}) - mode={mode}")
        self._persist_instance(instance)

        # Optional Grafana stub provisioning
        if (instance.recipe.grafana or {}).get("enabled", False):
            self._generate_grafana_dashboard_stub(instance)

        if mode == "local":
            # For now, run a synchronous local collection once and export to file
            try:
                self._run_local_collection_once(instance)
                instance.status = MonitorStatus.RUNNING
            except Exception as exc:
                instance.status = MonitorStatus.ERROR
                logger.exception(f"Local collection failed for {monitor_id}: {exc}")
        elif mode == "slurm":
            # Submit a stub SLURM job
            self.submit_slurm_job_stub(instance)
            instance.status = MonitorStatus.RUNNING
        else:
            instance.status = MonitorStatus.ERROR
            logger.error(f"Unknown monitor mode: {mode}")
        self._persist_instance(instance)
        return instance

    def stop_monitor(self, monitor_id: str) -> bool:
        inst = self._instances.get(monitor_id)
        if not inst:
            inst = self._load_instance_from_disk(monitor_id)
            if not inst:
                return False
        inst.status = MonitorStatus.STOPPED
        logger.info(f"Monitor stopped: {monitor_id}")
        self._persist_instance(inst)
        return True

    def export_metrics(self, monitor_id: str, output: Optional[str] = None) -> Path:
        inst = self._instances.get(monitor_id)
        if not inst:
            inst = self._load_instance_from_disk(monitor_id)
        if not inst:
            raise ValueError(f"Monitor not found: {monitor_id}")
        # Export last captured metrics if present; else re-collect once
        return self._run_local_collection_once(inst, output_override=output)

    # ----- Local collection -----
    def _run_local_collection_once(
        self, instance: MonitorInstance, output_override: Optional[str] = None
    ) -> Path:
        if psutil is None:
            raise RuntimeError("psutil not installed; cannot run local monitor")

        interval = max(1, int(instance.recipe.collection_interval_seconds))
        snapshot = {
            "monitor_id": instance.id,
            "taken_at": datetime.utcnow().isoformat() + "Z",
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": dict(psutil.virtual_memory()._asdict()),
            "disk": dict(psutil.disk_usage("/")._asdict()),
            "net_io": dict(psutil.net_io_counters()._asdict()),
            "pids": len(psutil.pids()),
            "targets": list(instance.targets),
        }

        out_dir = self.output_root / "monitors" / instance.id
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = Path(output_override) if output_override else out_dir / "metrics.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        logger.info(f"Wrote monitor metrics: {output_path}")
        time.sleep(interval)
        return output_path

    # ----- Stubs for HPC/Grafana/Prometheus -----
    def deploy_prometheus_stub(self, instance: MonitorInstance) -> None:
        logger.info("Prometheus deployment stub - not implemented")

    def deploy_grafana_stub(self, instance: MonitorInstance) -> None:
        logger.info("Grafana deployment stub - not implemented")

    def submit_slurm_job_stub(self, instance: MonitorInstance) -> None:
        logger.info("SLURM submission stub - not implemented")

    def _generate_grafana_dashboard_stub(self, instance: MonitorInstance) -> Path:
        """Create a minimal Grafana dashboard JSON stub and set a placeholder URL."""
        out_dir = self.output_root / "monitors" / instance.id
        out_dir.mkdir(parents=True, exist_ok=True)
        dashboard = {
            "title": f"UBenchAI - {instance.recipe.name}",
            "panels": [
                {"type": "graph", "title": "CPU % (local)", "targets": []},
                {"type": "graph", "title": "Memory (local)", "targets": []},
            ],
            "timezone": "browser",
        }
        path = out_dir / "grafana-dashboard.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, indent=2)
        # Placeholder URL users can import the dashboard into local Grafana
        instance.grafana_url = "http://localhost:3000"
        logger.info(f"Wrote Grafana dashboard stub: {path}")
        return path

    # ----- Persistence helpers -----
    def _instance_dir(self, instance_id: str) -> Path:
        return self.output_root / "monitors" / instance_id

    def _persist_instance(self, instance: MonitorInstance) -> None:
        out_dir = self._instance_dir(instance.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = instance.to_dict()
        with open(out_dir / "instance.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _load_existing_instances(self) -> None:
        monitors_root = self.output_root / "monitors"
        if not monitors_root.exists():
            return
        for child in monitors_root.iterdir():
            if not child.is_dir():
                continue
            inst = self._load_instance_from_disk(child.name)
            if inst:
                self._instances[inst.id] = inst

    def _load_instance_from_disk(self, instance_id: str) -> Optional[MonitorInstance]:
        inst_dir = self._instance_dir(instance_id)
        meta_path = inst_dir / "instance.json"
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data: Dict = json.load(f)
            recipe_name = (data.get("recipe") or {}).get("name")
            if not recipe_name:
                return None
            recipe: MonitorRecipe = self.recipe_loader.load_recipe(recipe_name)
            status_raw = data.get("status") or MonitorStatus.RUNNING
            status = (
                status_raw
                if isinstance(status_raw, MonitorStatus)
                else MonitorStatus(str(status_raw))
            )
            inst = MonitorInstance(
                id=str(data.get("id")),
                recipe=recipe,
                status=status,
                created_at_iso=str(data.get("created_at")),
                prometheus_url=data.get("prometheus_url"),
                grafana_url=data.get("grafana_url"),
                targets=list(data.get("targets") or []),
                metadata=dict(data.get("metadata") or {}),
            )
            return inst
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to load monitor instance {instance_id}: {exc}")
            return None


