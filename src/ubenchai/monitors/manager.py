"""
MonitorManager - central component to start/stop and manage monitoring runs.
Implements local collection, file export, and stubs for Prometheus/Grafana/SLURM.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
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

        # Deploy Prometheus if requested via exporters
        try:
            if any(
                (e.get("type") or "").lower() == "prometheus"
                for e in instance.recipe.exporters
            ):
                self.deploy_prometheus(instance)
        except Exception as exc:
            logger.warning(f"Prometheus deployment failed: {exc}")

        # Optional Grafana provisioning (binds Prometheus if available)
        try:
            if (instance.recipe.grafana or {}).get("enabled", False):
                self.deploy_grafana(instance)
        except Exception as exc:
            logger.warning(f"Grafana provisioning failed: {exc}")

        if mode == "local":
            # For now, run a synchronous local collection once and export to file
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
        output_path = (
            Path(output_override) if output_override else out_dir / "metrics.json"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        logger.info(f"Wrote monitor metrics: {output_path}")
        time.sleep(interval)
        return output_path

    # ----- Prometheus deployment -----
    def deploy_prometheus(self, instance: MonitorInstance) -> None:
        out_dir = self.output_root / "monitors" / instance.id
        prom_dir = out_dir / "prometheus"
        prom_dir.mkdir(parents=True, exist_ok=True)

        # Build scrape targets (host:port pairs)
        targets = []
        for t in instance.targets:
            # Accept raw host or host:port; default to 9090/9100 based on hint
            if ":" in t:
                targets.append(t)
            else:
                targets.append(f"{t}:9100")  # default to node_exporter

        config = {
            "global": {
                "scrape_interval": f"{max(1, int(instance.recipe.collection_interval_seconds))}s"
            },
            "scrape_configs": [
                {
                    "job_name": instance.recipe.name,
                    "static_configs": [{"targets": targets}] if targets else [],
                }
            ],
        }

        config_path = prom_dir / "prometheus.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False)

        # Try to start a local Prometheus if available
        prometheus_bin = self._which(["prometheus"])
        if prometheus_bin:
            data_dir = prom_dir / "data"
            data_dir.mkdir(exist_ok=True)
            log_path = prom_dir / "prometheus.log"
            try:
                import subprocess

                cmd = [
                    prometheus_bin,
                    f"--config.file={config_path}",
                    f"--storage.tsdb.path={data_dir}",
                    "--web.listen-address=0.0.0.0:9090",
                ]
                subprocess.Popen(
                    cmd,
                    stdout=open(log_path, "a"),
                    stderr=subprocess.STDOUT,
                )
                instance.prometheus_url = "http://localhost:9090"
                logger.info("Started local Prometheus on http://localhost:9090")
            except Exception as exc:
                logger.warning(f"Failed to start Prometheus automatically: {exc}")
        else:
            logger.info("Prometheus binary not found on PATH; wrote config only")
            # Provide a conventional URL for external Prometheus
            instance.prometheus_url = instance.prometheus_url or "http://localhost:9090"

        self._persist_instance(instance)

    # ----- Grafana provisioning -----
    def deploy_grafana(self, instance: MonitorInstance) -> None:
        out_dir = self.output_root / "monitors" / instance.id / "grafana"
        prov_dir = out_dir / "provisioning"
        ds_dir = prov_dir / "datasources"
        db_dir = prov_dir / "dashboards"
        dashboards_dir = out_dir / "dashboards"
        ds_dir.mkdir(parents=True, exist_ok=True)
        db_dir.mkdir(parents=True, exist_ok=True)
        dashboards_dir.mkdir(parents=True, exist_ok=True)

        # Data source binding to Prometheus
        prometheus_url = instance.prometheus_url or "http://localhost:9090"
        datasource_yaml = {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "UBenchAI Prometheus",
                    "type": "prometheus",
                    "access": "proxy",
                    "url": prometheus_url,
                    "isDefault": True,
                }
            ],
        }
        with open(ds_dir / "datasource.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(datasource_yaml, f, sort_keys=False)

        # Generate a simple dashboard
        dashboard_path = dashboards_dir / "ubenchai-overview.json"
        dashboard = {
            "annotations": {"list": []},
            "panels": [
                {
                    "type": "timeseries",
                    "title": "Node CPU Utilization",
                    "targets": [
                        {
                            "expr": '100 - (avg by(instance)(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
                        }
                    ],
                    "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
                },
            ],
            "title": f"UBenchAI - {instance.recipe.name}",
            "schemaVersion": 38,
            "version": 1,
        }
        with open(dashboard_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, indent=2)

        dashboards_prov = {
            "apiVersion": 1,
            "providers": [
                {
                    "name": "ubenchai-dashboards",
                    "orgId": 1,
                    "folder": "UBenchAI",
                    "type": "file",
                    "disableDeletion": False,
                    "options": {"path": str(dashboards_dir)},
                }
            ],
        }
        with open(db_dir / "dashboards.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(dashboards_prov, f, sort_keys=False)

        # Try to start Grafana if available
        grafana_bin = self._which(
            ["grafana-server", "grafana-server.exe"]
        )  # Windows-friendly
        if grafana_bin:
            try:
                import subprocess

                log_path = out_dir / "grafana.log"
                http_port = (instance.recipe.grafana or {}).get("port", 3000)
                env = {
                    **os.environ,
                    "GF_PATHS_PROVISIONING": str(prov_dir),
                    "GF_SERVER_HTTP_PORT": str(http_port),
                }
                subprocess.Popen(
                    [grafana_bin, f"--homepath={out_dir}"],
                    env=env,
                    stdout=open(log_path, "a"),
                    stderr=subprocess.STDOUT,
                )
                instance.grafana_url = f"http://localhost:{http_port}"
                logger.info(f"Started local Grafana on {instance.grafana_url}")
            except Exception as exc:
                logger.warning(f"Failed to start Grafana automatically: {exc}")
                instance.grafana_url = instance.grafana_url or "http://localhost:3000"
        else:
            logger.info("grafana-server not found; wrote provisioning files only")
            instance.grafana_url = instance.grafana_url or "http://localhost:3000"

        self._persist_instance(instance)

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
