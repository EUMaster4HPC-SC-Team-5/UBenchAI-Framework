"""
MonitorManager - central component to start/stop and manage monitoring runs.
Implements local collection, Prometheus/Grafana integration, and SLURM deployment.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, UTC
import os
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
import yaml

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # Fallback if not installed; local collector will error politely

from .models import MonitorInstance, MonitorRecipe, MonitorStatus
from .recipe_loader import MonitorRecipeLoader
from .prometheus_client import PrometheusClient
from .grafana_client import GrafanaClient


class MonitorManager:
    def __init__(self, recipe_directory: str = "recipes", output_root: str = "logs"):
        self.recipe_directory = Path(recipe_directory)
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.recipe_loader = MonitorRecipeLoader(recipe_directory)
        self._instances: Dict[str, MonitorInstance] = {}

        # Initialize clients
        self.prometheus = PrometheusClient(self.output_root)
        self.grafana = GrafanaClient(self.output_root)

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
        created_at_iso = datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
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

        # Deploy monitoring stack
        try:
            if any(e.get("type") == "prometheus" for e in instance.recipe.exporters):
                # Create Prometheus config from recipe
                prometheus_config = self._build_prometheus_config(instance)

                # Deploy Prometheus
                instance.prometheus_url = self.prometheus.deploy_prometheus(
                    instance_id=monitor_id, config=prometheus_config
                )

                # Wait for Prometheus to be ready before deploying Grafana
                if instance.prometheus_url and not self.prometheus.wait_for_ready(
                    instance.prometheus_url
                ):
                    raise RuntimeError(
                        f"Prometheus failed to become ready at {instance.prometheus_url}"
                    )
                elif not instance.prometheus_url:
                    logger.warning(
                        "Prometheus binary not available, skipping Prometheus deployment"
                    )

                # Deploy Grafana if enabled and Prometheus is available
                if instance.recipe.grafana.get("enabled", False):
                    if instance.prometheus_url:
                        instance.grafana_url = self.grafana.deploy_grafana(
                            instance_id=monitor_id,
                            prometheus_url=instance.prometheus_url,
                            config=instance.recipe.grafana,
                        )

                        # Test the connection between Grafana and Prometheus
                        admin_user = instance.recipe.grafana.get("admin_user", "admin")
                        admin_password = instance.recipe.grafana.get(
                            "admin_password", "admin"
                        )

                        if not self.grafana._test_datasource_connection(
                            instance.grafana_url, admin_user, admin_password
                        ):
                            logger.warning(
                                "Grafana-Prometheus connection test failed, but continuing..."
                            )

                        # Create dashboards
                        for dashboard in instance.recipe.grafana.get("dashboards", []):
                            if dashboard["type"] == "system":
                                self.grafana.create_system_dashboard(
                                    instance_id=monitor_id, targets=instance.targets
                                )
                            elif dashboard["type"] == "llm":
                                self.grafana.create_llm_dashboard(
                                    instance_id=monitor_id
                                )
                    else:
                        logger.warning(
                            "Grafana is enabled but Prometheus is not available, skipping Grafana deployment"
                        )

                logger.info(
                    f"Deployed monitoring stack for {monitor_id}:"
                    f"\n  Prometheus: {instance.prometheus_url}"
                    f"\n  Grafana: {instance.grafana_url or 'disabled'}"
                )

        except Exception as e:
            logger.error(f"Failed to deploy monitoring stack: {e}")
            instance.status = MonitorStatus.ERROR
            self._persist_instance(instance)
            raise

        # Run local collection if needed
        if mode == "local" and not instance.prometheus_url:
            try:
                self._run_local_collection_once(instance)
                instance.status = MonitorStatus.RUNNING
            except Exception as exc:
                instance.status = MonitorStatus.ERROR
                logger.exception(f"Local collection failed for {monitor_id}: {exc}")
        elif mode == "slurm":
            # Submit a real SLURM job (best-effort)
            self.submit_slurm_job(instance)
            instance.status = MonitorStatus.RUNNING
        elif instance.prometheus_url:
            # Prometheus is available and running
            instance.status = MonitorStatus.RUNNING
        else:
            # No Prometheus and no local collection
            logger.warning(f"Monitor {monitor_id} has no active collection method")
            instance.status = (
                MonitorStatus.RUNNING
            )  # Still mark as running since config was written

        self._persist_instance(instance)
        return instance

    def stop_monitor(self, monitor_id: str) -> bool:
        inst = self._instances.get(monitor_id)
        if not inst:
            inst = self._load_instance_from_disk(monitor_id)
            if not inst:
                return False

        # Attempt to tear down SLURM job if recorded
        job_id = (inst.metadata or {}).get("slurm_job_id")
        if job_id:
            try:
                import subprocess

                subprocess.run(
                    ["scancel", str(job_id)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                logger.info(f"Cancelled SLURM job {job_id} for monitor {monitor_id}")
            except Exception as exc:
                logger.warning(f"Failed to cancel SLURM job {job_id}: {exc}")

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
            "taken_at": datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": dict(psutil.virtual_memory()._asdict()),
            "disk": dict(psutil.disk_usage("/")._asdict()),
            "net_io": dict(psutil.net_io_counters()._asdict()),
            "pids": len(psutil.pids()),
            "targets": list(instance.targets),
        }

        out_dir = self.output_root / "monitors" / instance.id
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = (
            Path(output_override) if output_override else out_dir / "metrics.json"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        logger.info(f"Wrote monitor metrics: {output_path}")
        time.sleep(interval)
        return output_path

    def _build_prometheus_config(self, instance: MonitorInstance) -> Dict:
        """Build Prometheus configuration from recipe."""
        # Get prometheus config from recipe
        prom_config = next(
            (e for e in instance.recipe.exporters if e.get("type") == "prometheus"), {}
        )

        # Build base config
        config = {
            "global": {
                "scrape_interval": f"{instance.recipe.collection_interval_seconds}s",
                "evaluation_interval": "15s",
            },
            "scrape_configs": prom_config.get("scrape_configs", []),
        }

        # Add default node_exporter job if none specified
        if not any(j.get("job_name") == "node" for j in config["scrape_configs"]):
            config["scrape_configs"].append(
                {
                    "job_name": "node",
                    "static_configs": [
                        {"targets": [f"{t}:9100" for t in instance.targets]}
                    ],
                }
            )

        return config

    # ----- SLURM job submission (monitor context) -----
    def submit_slurm_job(self, instance: MonitorInstance) -> None:
        """Submit a lightweight SLURM job to validate lifecycle management.

        Tries to run node_exporter if available on the cluster; otherwise runs a short sleep.
        Records job id in instance.metadata['slurm_job_id'].
        """
        try:
            import subprocess, tempfile
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"System missing subprocess/tempfile: {exc}")

        # Check if SLURM is available first
        try:
            subprocess.run(
                ["sbatch", "--version"], capture_output=True, text=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(
                "SLURM not available on this system - skipping SLURM job submission"
            )
            logger.info("Monitor will run in local mode instead")
            # Fall back to local collection
            try:
                self._run_local_collection_once(instance)
                instance.metadata["slurm_fallback"] = "local_collection"
                logger.info("Completed local collection as SLURM fallback")
            except Exception as exc:
                logger.warning(f"Local collection fallback also failed: {exc}")
            return

        # Compose a minimal sbatch script
        script_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=mon-{instance.recipe.name}",
            "#SBATCH --time=00:10:00",
            "#SBATCH --output=/tmp/ubenchai_mon_%j.out",
            "#SBATCH --error=/tmp/ubenchai_mon_%j.err",
            "\n",
            "if command -v node_exporter >/dev/null 2>&1; then",
            "  node_exporter &",
            "  PID=$!",
            '  echo "node_exporter started with PID $PID"',
            "  sleep 300",
            "  kill $PID",
            "else",
            "  echo 'node_exporter not found; sleeping as placeholder'",
            "  sleep 60",
            "fi",
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("\n".join(script_lines))
            script_path = f.name

        try:
            result = subprocess.run(
                ["sbatch", script_path], capture_output=True, text=True, check=True
            )
            output = result.stdout.strip()
            job_id = output.split()[-1]
            instance.metadata["slurm_job_id"] = job_id
            logger.info(f"SLURM monitor job submitted: {job_id}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"sbatch failed: {e.stderr}")
        finally:
            try:
                import os as _os

                _os.unlink(script_path)
            except Exception:
                pass

        self._persist_instance(instance)

    # ----- Utility helpers -----
    def _which(self, candidates: List[str]) -> Optional[str]:
        """Return first executable found on PATH from candidates."""
        import shutil

        for name in candidates:
            path = shutil.which(name)
            if path:
                return path
        return None

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
