"""
HealthResolver - Resolves and validates service endpoints
"""

import subprocess
import os
from typing import Optional, Dict
import requests
from loguru import logger

from ubenchai.clients.recipes import ClientRecipe, TargetSpec


class HealthResolver:
    """
    Resolves and validates server endpoints before client execution.
    Performs connectivity checks to ensure the target is reachable.
    """

    def __init__(self):
        """Initialize HealthResolver"""
        logger.info("HealthResolver initialized")

    def resolve_endpoint(self, recipe: ClientRecipe) -> TargetSpec:
        """
        Resolve target endpoint from recipe

        Args:
            recipe: ClientRecipe with target specification

        Returns:
            TargetSpec with resolved endpoint

        Raises:
            ValueError: If endpoint cannot be resolved
        """
        target = recipe.target

        # If direct endpoint is provided, use it
        if target.endpoint:
            logger.info(f"Using direct endpoint: {target.endpoint}")
            return target

        # Otherwise, try to find service by name
        if target.service:
            logger.info(f"Resolving endpoint for service: {target.service}")
            endpoint = self._find_service_by_name(target.service)

            if endpoint:
                # Create new target with resolved endpoint
                resolved_target = TargetSpec(
                    service=target.service,
                    endpoint=endpoint,
                    protocol=target.protocol,
                    timeout_seconds=target.timeout_seconds,
                )
                return resolved_target

        raise ValueError(f"Cannot resolve endpoint for target: {target}")

    def _find_service_by_name(self, service_name: str) -> Optional[str]:
        """
        Find service endpoint by querying SLURM for running jobs

        Args:
            service_name: Name of the service (e.g., "ollama-llm")

        Returns:
            Endpoint URL if found, None otherwise
        """
        try:
            # Query SLURM for user's running jobs
            username = os.getenv("USER")
            result = subprocess.run(
                [
                    "squeue",
                    "-u",
                    username,
                    "--format=%i|%j|%R",
                    "--noheader",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse output to find matching service
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) != 3:
                    continue

                job_id, job_name, node = parts

                # Check if job name matches service name
                if service_name in job_name:
                    # Construct endpoint
                    # TODO: Get port from recipe or config
                    endpoint = f"http://{node}:11434"
                    logger.info(
                        f"Found service {service_name} on {node} (job {job_id})"
                    )
                    return endpoint

            logger.warning(f"Service {service_name} not found in running jobs")
            return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to query SLURM: {e}")
            return None
        except Exception as e:
            logger.error(f"Error finding service: {e}")
            return None

    def check_connectivity(self, target: TargetSpec) -> bool:
        """
        Check if target endpoint is reachable

        Args:
            target: TargetSpec with endpoint

        Returns:
            True if reachable, False otherwise
        """
        if not target.endpoint:
            logger.error("No endpoint specified for connectivity check")
            return False

        logger.info(f"Checking connectivity to: {target.endpoint}")

        if target.protocol in ["http", "https"]:
            return self._check_http_connectivity(target)
        else:
            logger.warning(f"Connectivity check not implemented for: {target.protocol}")
            return False

    def _check_http_connectivity(self, target: TargetSpec) -> bool:
        """
        Check HTTP/HTTPS connectivity

        Args:
            target: TargetSpec with HTTP endpoint

        Returns:
            True if reachable, False otherwise
        """
        try:
            # Try to reach the endpoint
            url = target.endpoint
            if not url.startswith(("http://", "https://")):
                url = f"http://{url}"

            # Try a simple GET request
            response = requests.get(
                f"{url}/api/tags",  # Ollama-specific endpoint
                timeout=target.timeout_seconds,
            )

            if response.status_code == 200:
                logger.info(f"Successfully connected to {url}")
                return True
            else:
                logger.warning(
                    f"Endpoint reachable but returned status {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to {target.endpoint}: {e}")
            return False

    def read_server_endpoint_file(self, path: str) -> Optional[TargetSpec]:
        """
        Read server endpoint information from a file
        (Alternative method for service discovery)

        Args:
            path: Path to endpoint info file

        Returns:
            TargetSpec if found, None otherwise
        """
        # TODO: Implement if needed
        logger.debug(f"Reading endpoint file: {path}")
        return None

    def get_all_running_services(self) -> Dict[str, str]:
        """
        Get all running services and their endpoints

        Returns:
            Dictionary mapping service names to endpoints
        """
        services = {}

        try:
            username = os.getenv("USER")
            result = subprocess.run(
                [
                    "squeue",
                    "-u",
                    username,
                    "--format=%i|%j|%R",
                    "--noheader",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) == 3:
                    job_id, job_name, node = parts
                    endpoint = f"http://{node}:11434"
                    services[job_name] = endpoint

            logger.info(f"Found {len(services)} running services")
            return services

        except Exception as e:
            logger.error(f"Error getting running services: {e}")
            return {}