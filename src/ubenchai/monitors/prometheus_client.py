"""
PrometheusClient - Handles Prometheus deployment, configuration and querying.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml

from loguru import logger


class PrometheusClient:
    """Client for managing Prometheus instances and querying metrics."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.config_dir = workspace_root / "prometheus"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def deploy_prometheus(self, instance_id: str, config: dict) -> Optional[str]:
        """Deploy Prometheus instance with given configuration.

        Args:
            instance_id: Unique identifier for this Prometheus instance
            config: Dictionary containing Prometheus configuration including:
                - scrape_interval: How frequently to scrape targets
                - evaluation_interval: How frequently to evaluate rules
                - scrape_configs: List of jobs to scrape

        Returns:
            URL where Prometheus UI can be accessed, or None if deployment failed
        """
        instance_dir = self.config_dir / instance_id
        instance_dir.mkdir(parents=True, exist_ok=True)

        # Write prometheus.yml
        config_path = instance_dir / "prometheus.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False)

        # Create data directory
        data_dir = instance_dir / "data"
        data_dir.mkdir(exist_ok=True)

        # Submit as SLURM job if in HPC environment
        if os.environ.get("SLURM_JOB_ID"):
            return self._deploy_slurm(instance_id, config_path, data_dir)
        else:
            return self._deploy_local(instance_id, config_path, data_dir)

    def _deploy_local(
        self, instance_id: str, config_path: Path, data_dir: Path
    ) -> Optional[str]:
        """Deploy Prometheus locally for development/testing."""
        prometheus_bin = self._which(["prometheus"])
        if not prometheus_bin:
            logger.warning("Prometheus binary not found, configuration written only")
            return None  # No URL since no process started

        log_path = self.config_dir / instance_id / "prometheus.log"
        cmd = [
            prometheus_bin,
            f"--config.file={config_path}",
            f"--storage.tsdb.path={data_dir}",
            "--web.listen-address=0.0.0.0:9090",
            "--web.enable-admin-api",  # Enable admin API for configuration
            "--web.enable-lifecycle",  # Enable reloading config via HTTP POST
        ]

        subprocess.Popen(
            cmd,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
        )

        logger.info(f"Started Prometheus locally for instance {instance_id}")
        return "http://localhost:9090"

    def _deploy_slurm(self, instance_id: str, config_path: Path, data_dir: Path) -> str:
        """Deploy Prometheus as a SLURM job."""
        slurm_script = f"""#!/bin/bash
#SBATCH --job-name=prom-{instance_id}
#SBATCH --output={self.config_dir}/{instance_id}/slurm-%j.out
#SBATCH --error={self.config_dir}/{instance_id}/slurm-%j.err
#SBATCH --time=24:00:00

# Load required modules
module load prometheus

# Start Prometheus
prometheus --config.file={config_path} \\
          --storage.tsdb.path={data_dir} \\
          --web.listen-address=0.0.0.0:9090 \\
          --web.enable-admin-api \\
          --web.enable-lifecycle
"""
        script_path = self.config_dir / instance_id / "start_prometheus.sh"
        with open(script_path, "w") as f:
            f.write(slurm_script)

        # Submit job
        result = subprocess.run(
            ["sbatch", str(script_path)], capture_output=True, text=True, check=True
        )
        job_id = result.stdout.strip().split()[-1]
        logger.info(
            f"Submitted Prometheus SLURM job {job_id} for instance {instance_id}"
        )

        # Return URL based on allocated node
        squeue_output = subprocess.run(
            ["squeue", "-j", job_id, "-o", "%N"],
            capture_output=True,
            text=True,
            check=True,
        )
        node = squeue_output.stdout.strip().split("\n")[-1]
        return f"http://{node}:9090"

    def query(self, url: str, query: str) -> Dict:
        """Execute an instant PromQL query."""
        import requests

        response = requests.get(f"{url}/api/v1/query", params={"query": query})
        response.raise_for_status()
        return response.json()

    def query_range(
        self,
        url: str,
        query: str,
        start: Union[int, datetime],
        end: Union[int, datetime],
        step: str = "15s",
    ) -> Dict:
        """Execute a range PromQL query over a time window."""
        import requests

        # Convert datetime objects to Unix timestamps if needed
        if isinstance(start, datetime):
            start = int(start.timestamp())
        if isinstance(end, datetime):
            end = int(end.timestamp())

        response = requests.get(
            f"{url}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
        )
        response.raise_for_status()
        return response.json()

    def reload_config(self, url: str) -> bool:
        """Reload Prometheus configuration without restart."""
        import requests

        try:
            response = requests.post(f"{url}/-/reload")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to reload Prometheus config: {e}")
            return False

    def get_targets(self, url: str) -> Dict:
        """Get current scrape targets and their status."""
        import requests

        response = requests.get(f"{url}/api/v1/targets")
        response.raise_for_status()
        return response.json()

    def health_check(self, url: str) -> bool:
        """Check if Prometheus is healthy."""
        import requests

        try:
            response = requests.get(f"{url}/-/healthy", timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Prometheus health check failed: {e}")
            return False

    def wait_for_ready(
        self, url: str, timeout: int = 60, retry_interval: int = 5
    ) -> bool:
        """Wait for Prometheus to become ready with retry logic.

        Args:
            url: URL of Prometheus instance
            timeout: Maximum time to wait in seconds
            retry_interval: Time between retries in seconds

        Returns:
            True if Prometheus becomes ready, False otherwise
        """
        import requests

        logger.info(f"Waiting for Prometheus at {url} to become ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check both health and ready endpoints
                health_response = requests.get(f"{url}/-/healthy", timeout=5)
                ready_response = requests.get(f"{url}/-/ready", timeout=5)

                if (
                    health_response.status_code == 200
                    and ready_response.status_code == 200
                ):
                    logger.info(f"Prometheus is ready at {url}")
                    return True

            except requests.exceptions.RequestException as e:
                logger.debug(f"Prometheus not ready yet: {e}")

            logger.debug(
                f"Retrying Prometheus readiness check in {retry_interval} seconds..."
            )
            time.sleep(retry_interval)

        logger.error(
            f"Prometheus at {url} did not become ready within {timeout} seconds"
        )
        return False

    def _which(self, candidates: List[str]) -> Optional[str]:
        """Return first executable found on PATH from candidates."""
        import shutil

        for name in candidates:
            path = shutil.which(name)
            if path:
                return path
        return None
