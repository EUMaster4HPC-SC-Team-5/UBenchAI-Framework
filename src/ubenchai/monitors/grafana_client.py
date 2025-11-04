"""
GrafanaClient - Handles Grafana deployment, dashboard creation and data source configuration.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml
import requests

from loguru import logger


class GrafanaClient:
    """Client for managing Grafana instances and dashboards."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.config_dir = workspace_root / "grafana"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def deploy_grafana(
        self, instance_id: str, prometheus_url: str, config: Dict[str, any]
    ) -> str:
        """Deploy Grafana instance with given configuration.

        Args:
            instance_id: Unique identifier for this Grafana instance
            prometheus_url: URL of Prometheus instance to use as data source
            config: Dictionary containing Grafana configuration including:
                - port: HTTP port to listen on
                - admin_user: Admin username
                - admin_password: Admin password

        Returns:
            URL where Grafana UI can be accessed
        """
        # Validate Prometheus connection before proceeding
        if not self._wait_for_prometheus(prometheus_url):
            raise ConnectionError(
                f"Failed to connect to Prometheus at {prometheus_url}"
            )
        instance_dir = self.config_dir / instance_id
        prov_dir = instance_dir / "provisioning"
        ds_dir = prov_dir / "datasources"
        db_dir = prov_dir / "dashboards"
        dashboards_dir = instance_dir / "dashboards"

        # Create directory structure
        for d in [ds_dir, db_dir, dashboards_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Configure Prometheus data source with enhanced settings
        datasource = {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "UBenchAI Prometheus",
                    "type": "prometheus",
                    "access": "proxy",
                    "url": prometheus_url,
                    "isDefault": True,
                    "jsonData": {
                        "timeInterval": "15s",
                        "queryTimeout": "60s",
                        "httpMethod": "POST",
                        "keepCookies": [],
                    },
                    "secureJsonData": {},
                    "version": 1,
                    "readOnly": False,
                }
            ],
        }
        with open(ds_dir / "prometheus.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(datasource, f, sort_keys=False)

        # Configure dashboard provider
        dashboard_provider = {
            "apiVersion": 1,
            "providers": [
                {
                    "name": "UBenchAI Dashboards",
                    "orgId": 1,
                    "folder": "UBenchAI",
                    "type": "file",
                    "disableDeletion": False,
                    "updateIntervalSeconds": 10,
                    "options": {"path": str(dashboards_dir)},
                }
            ],
        }
        with open(db_dir / "dashboards.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(dashboard_provider, f, sort_keys=False)

        # Deploy based on environment
        if os.environ.get("SLURM_JOB_ID"):
            return self._deploy_slurm(instance_id, prov_dir, config)
        else:
            return self._deploy_local(instance_id, prov_dir, config)

    def _deploy_local(
        self, instance_id: str, prov_dir: Path, config: Dict[str, any]
    ) -> str:
        """Deploy Grafana locally for development/testing."""
        grafana_bin = self._which(["grafana-server", "grafana-server.exe"])
        if not grafana_bin:
            logger.warning("Grafana binary not found, configuration written only")
            return "http://localhost:3000"

        http_port = config.get("port", 3000)
        log_path = self.config_dir / instance_id / "grafana.log"

        env = {
            **os.environ,
            "GF_PATHS_PROVISIONING": str(prov_dir),
            "GF_SERVER_HTTP_PORT": str(http_port),
            "GF_SECURITY_ADMIN_USER": config.get("admin_user", "admin"),
            "GF_SECURITY_ADMIN_PASSWORD": config.get("admin_password", "admin"),
        }

        subprocess.Popen(
            [grafana_bin],
            env=env,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
        )

        logger.info(f"Started Grafana locally for instance {instance_id}")
        return f"http://localhost:{http_port}"

    def _deploy_slurm(
        self, instance_id: str, prov_dir: Path, config: Dict[str, any]
    ) -> str:
        """Deploy Grafana as a SLURM job."""
        http_port = config.get("port", 3000)

        slurm_script = f"""#!/bin/bash
#SBATCH --job-name=grafana-{instance_id}
#SBATCH --output={self.config_dir}/{instance_id}/slurm-%j.out
#SBATCH --error={self.config_dir}/{instance_id}/slurm-%j.err
#SBATCH --time=24:00:00

# Load required modules
module load grafana

# Set environment variables
export GF_PATHS_PROVISIONING={prov_dir}
export GF_SERVER_HTTP_PORT={http_port}
export GF_SECURITY_ADMIN_USER={config.get('admin_user', 'admin')}
export GF_SECURITY_ADMIN_PASSWORD={config.get('admin_password', 'admin')}

# Start Grafana
grafana-server
"""
        script_path = self.config_dir / instance_id / "start_grafana.sh"
        with open(script_path, "w") as f:
            f.write(slurm_script)

        # Submit job
        result = subprocess.run(
            ["sbatch", str(script_path)], capture_output=True, text=True, check=True
        )
        job_id = result.stdout.strip().split()[-1]
        logger.info(f"Submitted Grafana SLURM job {job_id} for instance {instance_id}")

        # Return URL based on allocated node
        squeue_output = subprocess.run(
            ["squeue", "-j", job_id, "-o", "%N"],
            capture_output=True,
            text=True,
            check=True,
        )
        node = squeue_output.stdout.strip().split("\n")[-1]
        return f"http://{node}:{http_port}"

    def create_dashboard(
        self,
        instance_id: str,
        title: str,
        panels: List[Dict],
        variables: Optional[List[Dict]] = None,
        refresh: str = "5s",
    ) -> Path:
        """Create a new Grafana dashboard.

        Args:
            instance_id: Grafana instance ID
            title: Dashboard title
            panels: List of panel configurations
            variables: Optional list of dashboard variables/templating
            refresh: Dashboard refresh interval

        Returns:
            Path to the created dashboard file
        """
        dashboard = {
            "id": None,
            "uid": None,
            "title": title,
            "tags": ["ubenchai"],
            "timezone": "browser",
            "refresh": refresh,
            "schemaVersion": 38,
            "version": 1,
            "panels": panels,
        }

        if variables:
            dashboard["templating"] = {"list": variables}

        dashboard_path = (
            self.config_dir / instance_id / "dashboards" / f"{title.lower()}.json"
        )
        with open(dashboard_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, indent=2)

        return dashboard_path

    def create_system_dashboard(self, instance_id: str, targets: List[str]) -> Path:
        """Create a system metrics dashboard showing CPU, memory, disk etc."""
        panels = [
            # CPU Usage Panel
            {
                "title": "CPU Usage",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "targets": [
                    {
                        "expr": "100 - (avg by(instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)",
                        "legendFormat": "{{instance}}",
                    }
                ],
            },
            # Memory Usage Panel
            {
                "title": "Memory Usage",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "targets": [
                    {
                        "expr": "(node_memory_MemTotal_bytes - node_memory_MemFree_bytes - node_memory_Buffers_bytes - node_memory_Cached_bytes) / node_memory_MemTotal_bytes * 100",
                        "legendFormat": "{{instance}}",
                    }
                ],
            },
            # Disk Usage Panel
            {
                "title": "Disk Usage",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "targets": [
                    {
                        "expr": "100 - ((node_filesystem_avail_bytes{mountpoint='/'} * 100) / node_filesystem_size_bytes{mountpoint='/'})",
                        "legendFormat": "{{instance}}",
                    }
                ],
            },
            # Network Traffic Panel
            {
                "title": "Network Traffic",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "targets": [
                    {
                        "expr": "rate(node_network_receive_bytes_total[5m])",
                        "legendFormat": "{{instance}} Receive",
                    },
                    {
                        "expr": "rate(node_network_transmit_bytes_total[5m])",
                        "legendFormat": "{{instance}} Transmit",
                    },
                ],
            },
        ]

        variables = [
            {
                "name": "node",
                "type": "query",
                "datasource": "UBenchAI Prometheus",
                "refresh": 2,
                "regex": "",
                "sort": 1,
                "query": "label_values(node_cpu_seconds_total, instance)",
            }
        ]

        return self.create_dashboard(
            instance_id=instance_id,
            title="System Metrics",
            panels=panels,
            variables=variables,
        )

    def create_llm_dashboard(self, instance_id: str) -> Path:
        """Create a dashboard for LLM inference monitoring."""
        panels = [
            # Request Rate Panel
            {
                "title": "Request Rate",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "targets": [
                    {"expr": "rate(requests_total[5m])", "legendFormat": "Requests/sec"}
                ],
            },
            # Latency Panel
            {
                "title": "Request Latency",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "targets": [
                    {
                        "expr": "histogram_quantile(0.50, sum(rate(request_latency_seconds_bucket[5m])) by (le))",
                        "legendFormat": "p50",
                    },
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(request_latency_seconds_bucket[5m])) by (le))",
                        "legendFormat": "p95",
                    },
                    {
                        "expr": "histogram_quantile(0.99, sum(rate(request_latency_seconds_bucket[5m])) by (le))",
                        "legendFormat": "p99",
                    },
                ],
            },
            # GPU Utilization Panel
            {
                "title": "GPU Utilization",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "targets": [
                    {"expr": "nvidia_gpu_duty_cycle", "legendFormat": "GPU {{gpu}}"}
                ],
            },
            # GPU Memory Panel
            {
                "title": "GPU Memory Usage",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "targets": [
                    {
                        "expr": "nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes * 100",
                        "legendFormat": "GPU {{gpu}}",
                    }
                ],
            },
        ]

        return self.create_dashboard(
            instance_id=instance_id, title="LLM Inference", panels=panels
        )

    def _wait_for_prometheus(
        self, prometheus_url: str, timeout: int = 60, retry_interval: int = 5
    ) -> bool:
        """Wait for Prometheus to become available with retry logic.

        Args:
            prometheus_url: URL of Prometheus instance
            timeout: Maximum time to wait in seconds
            retry_interval: Time between retries in seconds

        Returns:
            True if Prometheus becomes available, False otherwise
        """
        logger.info(
            f"Waiting for Prometheus at {prometheus_url} to become available..."
        )
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{prometheus_url}/-/healthy", timeout=10)
                if response.status_code == 200:
                    logger.info(f"Prometheus is healthy at {prometheus_url}")
                    return True
            except requests.exceptions.RequestException as e:
                logger.debug(f"Prometheus not ready yet: {e}")

            logger.info(
                f"Retrying Prometheus connection in {retry_interval} seconds..."
            )
            time.sleep(retry_interval)

        logger.error(
            f"Prometheus at {prometheus_url} did not become available within {timeout} seconds"
        )
        return False

    def _test_datasource_connection(
        self, grafana_url: str, admin_user: str, admin_password: str
    ) -> bool:
        """Test the Prometheus datasource connection in Grafana.

        Args:
            grafana_url: URL of Grafana instance
            admin_user: Admin username
            admin_password: Admin password

        Returns:
            True if datasource connection is successful, False otherwise
        """
        try:
            # Wait for Grafana to be ready
            for _ in range(12):  # Wait up to 60 seconds
                try:
                    response = requests.get(f"{grafana_url}/api/health", timeout=5)
                    if response.status_code == 200:
                        break
                except requests.exceptions.RequestException:
                    pass
                time.sleep(5)
            else:
                logger.error("Grafana did not become available")
                return False

            # Test datasource connection
            auth = (admin_user, admin_password)
            response = requests.get(
                f"{grafana_url}/api/datasources/name/UBenchAI%20Prometheus/health",
                auth=auth,
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "OK":
                    logger.info("Prometheus datasource connection test successful")
                    return True
                else:
                    logger.error(f"Datasource connection test failed: {result}")
                    return False
            else:
                logger.error(
                    f"Failed to test datasource connection: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error testing datasource connection: {e}")
            return False

    def health_check(self, url: str) -> bool:
        """Check if Grafana is healthy."""
        try:
            response = requests.get(f"{url}/api/health", timeout=10)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def _which(self, candidates: List[str]) -> Optional[str]:
        """Return first executable found on PATH from candidates."""
        import shutil

        for name in candidates:
            path = shutil.which(name)
            if path:
                return path
        return None
