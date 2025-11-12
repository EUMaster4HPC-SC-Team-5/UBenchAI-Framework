"""
MonitorManager - Central orchestration for monitoring stacks
"""

from typing import Dict, List, Optional
from pathlib import Path
import subprocess
import shutil
import time
from loguru import logger

from ubenchai.monitors.recipes import MonitorRecipe, TargetService
from ubenchai.monitors.instances import MonitorInstance, MonitorRegistry, MonitorStatus
from ubenchai.monitors.orchestrator import MonitorOrchestrator
from ubenchai.monitors.recipe_loader import MonitorRecipeLoader


class MonitorManager:
    """
    Central orchestration for monitoring stacks
    Similar to ServerManager but for monitoring components
    """

    def __init__(
        self,
        recipe_directory: str = "recipes/monitors",
        output_root: str = "logs/monitors",
        dashboards_directory: str = "dashboards",
    ):
        """
        Initialize MonitorManager

        Args:
            recipe_directory: Directory containing monitor recipes
            output_root: Root directory for monitor outputs
            dashboards_directory: Directory containing dashboard JSON files
        """
        logger.info("Initializing MonitorManager")

        # Initialize components
        self.recipe_loader = MonitorRecipeLoader(recipe_directory=recipe_directory)
        self.monitor_registry = MonitorRegistry()
        self.orchestrator = MonitorOrchestrator(log_directory=f"{output_root}/slurm")

        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.dashboards_directory = Path(dashboards_directory)

        logger.info("MonitorManager initialization complete")

    def start_monitor(
        self,
        recipe_name: str,
        target_job_ids: Optional[List[str]] = None,
    ) -> MonitorInstance:
        """
        Start a monitoring stack from a recipe

        Args:
            recipe_name: Name of the monitor recipe
            target_job_ids: Optional list of SLURM job IDs to monitor

        Returns:
            MonitorInstance for the started monitoring stack
        """
        logger.info(f"Starting monitor from recipe: {recipe_name}")

        # Load recipe
        try:
            recipe = self.recipe_loader.load_recipe(recipe_name)
        except FileNotFoundError:
            logger.error(f"Recipe not found: {recipe_name}")
            raise
        except ValueError as e:
            logger.error(f"Recipe validation failed: {e}")
            raise

        # Resolve target endpoints
        targets = self._resolve_targets(recipe.targets, target_job_ids)

        if not targets:
            raise RuntimeError("No valid targets found to monitor")

        logger.info(f"Resolved targets: {targets}")

        # Create monitor instance
        instance = MonitorInstance(recipe=recipe)

        # Setup directories
        instance_dir = self.output_root / instance.id
        prom_config_dir = instance_dir / "prometheus" / "config"
        prom_data_dir = instance_dir / "prometheus" / "data"
        grafana_prov_dir = instance_dir / "grafana" / "provisioning"
        grafana_data_dir = instance_dir / "grafana" / "data"
        grafana_dashboards_dir = instance_dir / "grafana" / "dashboards"

        for dir_path in [
            prom_config_dir,
            prom_data_dir,
            grafana_prov_dir,
            grafana_data_dir,
            grafana_dashboards_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Deploy Prometheus
        if recipe.prometheus.enabled:
            logger.info("Deploying Prometheus...")
            prom_job_id = self.orchestrator.deploy_prometheus(
                config=recipe.prometheus,
                targets=targets,
                config_dir=prom_config_dir,
                data_dir=prom_data_dir,
            )

            # Wait for Prometheus to be running and get its node
            logger.info("Waiting for Prometheus to be running...")
            prom_node = self._wait_for_job_node(prom_job_id, timeout_seconds=120)

            if not prom_node:
                logger.error("Prometheus failed to start or timeout reached")
                # Clean up the failed job
                try:
                    self.orchestrator.stop_component(prom_job_id)
                except Exception as e:
                    logger.warning(f"Failed to stop Prometheus job: {e}")
                raise RuntimeError("Prometheus failed to start or timeout reached")

            prom_url = f"http://{prom_node}:{recipe.prometheus.port}"
            instance.add_component("prometheus", prom_job_id, prom_url)
            logger.info(f"Prometheus deployed and running: {prom_url}")

        # Copy dashboard files to Grafana
        if recipe.grafana.enabled and recipe.grafana.dashboards:
            logger.info("Copying dashboard files...")
            self._copy_dashboards(recipe.grafana.dashboards, grafana_dashboards_dir)

        # Deploy Grafana
        if recipe.grafana.enabled:
            logger.info("Deploying Grafana...")

            # Wait a bit more for Prometheus to fully initialize
            logger.info("Waiting for Prometheus to fully initialize...")
            time.sleep(10)

            grafana_job_id = self.orchestrator.deploy_grafana(
                config=recipe.grafana,
                prometheus_url=instance.prometheus_url,
                provisioning_dir=grafana_prov_dir,
                data_dir=grafana_data_dir,
                dashboards_dir=grafana_dashboards_dir,
            )

            # Wait for Grafana to be running and get its node
            logger.info("Waiting for Grafana to be running...")
            grafana_node = self._wait_for_job_node(grafana_job_id, timeout_seconds=120)

            if not grafana_node:
                logger.error("Grafana failed to start or timeout reached")
                # Clean up both jobs
                try:
                    self.orchestrator.stop_component(grafana_job_id)
                    if recipe.prometheus.enabled:
                        self.orchestrator.stop_component(
                            instance.components["prometheus"].job_id
                        )
                except Exception as e:
                    logger.warning(f"Failed to stop components: {e}")
                raise RuntimeError("Grafana failed to start or timeout reached")

            grafana_url = f"http://{grafana_node}:{recipe.grafana.port}"
            instance.add_component("grafana", grafana_job_id, grafana_url)
            logger.info(f"Grafana deployed and running: {grafana_url}")

        # Register instance
        if not self.monitor_registry.register(instance):
            logger.error(f"Failed to register monitor: {instance.id}")
            # Cleanup
            self._cleanup_instance(instance)
            raise RuntimeError("Monitor registration failed")

        # Update status
        instance.update_status(MonitorStatus.RUNNING)

        logger.info(f"Monitor started successfully: {instance.id}")
        return instance

    def _copy_dashboards(
        self,
        dashboard_names: List[str],
        target_dir: Path,
    ) -> None:
        """
        Copy dashboard JSON files to Grafana dashboards directory

        Args:
            dashboard_names: List of dashboard names (e.g., ["vllm-metrics"])
            target_dir: Target directory for dashboard files
        """
        for dashboard_name in dashboard_names:
            source_file = self.dashboards_directory / f"{dashboard_name}.json"

            if not source_file.exists():
                logger.warning(f"Dashboard file not found: {source_file}")
                continue

            target_file = target_dir / f"{dashboard_name}.json"
            shutil.copy2(source_file, target_file)
            logger.info(f"Copied dashboard: {source_file} -> {target_file}")

    def stop_monitor(self, monitor_id: str) -> bool:
        """Stop a running monitor"""
        logger.info(f"Stopping monitor: {monitor_id}")

        instance = self.monitor_registry.get(monitor_id)
        if not instance:
            logger.error(f"Monitor not found: {monitor_id}")
            return False

        instance.update_status(MonitorStatus.STOPPING)

        # Stop all components
        success = True
        for name, component in instance.components.items():
            logger.info(f"Stopping component: {name} ({component.job_id})")
            if not self.orchestrator.stop_component(component.job_id):
                logger.error(f"Failed to stop component: {name}")
                success = False

        if success:
            instance.update_status(MonitorStatus.STOPPED)
            self.monitor_registry.unregister(monitor_id)
            logger.info(f"Monitor stopped successfully: {monitor_id}")
        else:
            instance.update_status(MonitorStatus.ERROR)
            logger.error(f"Failed to stop all components for monitor: {monitor_id}")

        return success

    def list_available_monitors(self) -> List[str]:
        """List available monitor recipes"""
        logger.info("Listing available monitor recipes")
        recipes = self.recipe_loader.list_available_recipes()
        logger.debug(f"Found {len(recipes)} available recipes")
        return recipes

    def list_running_monitors(self) -> List[Dict]:
        """List running monitor instances"""
        logger.info("Listing running monitors")
        instances = self.monitor_registry.get_all()
        return [instance.to_dict() for instance in instances]

    def get_monitor_status(self, monitor_id: str) -> Dict:
        """Get status of a monitor"""
        logger.info(f"Getting status for monitor: {monitor_id}")

        instance = self.monitor_registry.get(monitor_id)
        if not instance:
            raise ValueError(f"Monitor not found: {monitor_id}")

        # Update component statuses
        for name, component in instance.components.items():
            status = self.orchestrator.get_component_status(component.job_id)
            component.status = status

        return instance.to_dict()

    def get_recipe_info(self, recipe_name: str) -> Dict:
        """Get information about a recipe"""
        return self.recipe_loader.get_recipe_info(recipe_name)

    def _resolve_targets(
        self,
        target_specs: List[TargetService],
        job_ids: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Resolve target services to endpoints

        Returns:
            Dict of {job_name: "host:port"}
        """
        targets = {}

        for spec in target_specs:
            # If job_id provided, use it
            if job_ids and len(job_ids) > 0:
                job_id = job_ids[0]
                # Wait for the target job to be running
                node = self._wait_for_job_node(job_id, timeout_seconds=60)
                if node:
                    targets[spec.name] = f"{node}:{spec.port}"
                    logger.info(f"Resolved {spec.name} -> {node}:{spec.port}")
                else:
                    logger.warning(f"Could not resolve node for job {job_id}")
            # If endpoint directly specified
            elif spec.endpoint:
                targets[spec.name] = spec.endpoint
                logger.info(f"Using direct endpoint for {spec.name}: {spec.endpoint}")
            # Try to find by service name
            elif spec.job_id:
                node = self._wait_for_job_node(spec.job_id, timeout_seconds=60)
                if node:
                    targets[spec.name] = f"{node}:{spec.port}"
                    logger.info(f"Resolved {spec.name} -> {node}:{spec.port}")

        return targets

    def _get_job_node(self, job_id: str) -> Optional[str]:
        """Get the node where a SLURM job is running (immediate check, no waiting)"""
        try:
            result = subprocess.run(
                ["squeue", "-j", job_id, "--format=%N", "--noheader"],
                capture_output=True,
                text=True,
                check=True,
            )

            node = result.stdout.strip()
            return node if node else None

        except subprocess.CalledProcessError:
            logger.warning(f"Could not find node for job: {job_id}")
            return None

    def _wait_for_job_node(
        self, job_id: str, timeout_seconds: int = 120
    ) -> Optional[str]:
        """
        Wait for a SLURM job to be running and return its node

        Args:
            job_id: SLURM job ID
            timeout_seconds: Maximum time to wait (default: 120 seconds)

        Returns:
            Node hostname if job is running, None if timeout or job failed
        """
        start_time = time.time()
        last_status = None

        logger.info(
            f"Waiting for job {job_id} to be running (timeout: {timeout_seconds}s)..."
        )

        while (time.time() - start_time) < timeout_seconds:
            try:
                result = subprocess.run(
                    ["squeue", "-j", job_id, "--format=%T|%N", "--noheader"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                output = result.stdout.strip()
                if not output:
                    logger.warning(f"Job {job_id} not found in queue")
                    return None

                parts = output.split("|")
                if len(parts) >= 2:
                    status, node = parts[0].strip(), parts[1].strip()

                    # Log status changes
                    if status != last_status:
                        logger.info(f"Job {job_id} status: {status}")
                        last_status = status

                    if status == "RUNNING" and node:
                        elapsed = time.time() - start_time
                        logger.info(
                            f"✓ Job {job_id} is running on node {node} (took {elapsed:.1f}s)"
                        )
                        return node
                    elif status == "PENDING":
                        logger.debug(f"Job {job_id} is pending, waiting...")
                    elif status in ["FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL"]:
                        logger.error(f"✗ Job {job_id} failed with status {status}")
                        return None

            except subprocess.CalledProcessError as e:
                logger.warning(f"Error checking job {job_id}: {e}")

            time.sleep(5)  # Wait 5 seconds before next check

        elapsed = time.time() - start_time
        logger.error(
            f"✗ Timeout waiting for job {job_id} to start (waited {elapsed:.1f}s)"
        )
        return None

    def _cleanup_instance(self, instance: MonitorInstance) -> None:
        """Cleanup a failed instance"""
        for name, component in instance.components.items():
            try:
                self.orchestrator.stop_component(component.job_id)
            except Exception as e:
                logger.error(f"Error cleaning up component {name}: {e}")
