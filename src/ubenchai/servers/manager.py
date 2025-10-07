"""
ServerManager - Central orchestration for containerized AI services
"""

from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from ubenchai.servers.services import (
    ServiceInstance,
    ServiceRegistry,
    ServiceStatus,
)
from ubenchai.servers.orchestrator import OrchestratorType
from ubenchai.servers.slurm_orchestrator import SlurmOrchestrator
from ubenchai.servers.recipe_loader import RecipeLoader


class ServerManager:
    """
    Central orchestration component that manages the complete lifecycle
    of containerized AI services.

    Coordinates between recipe loading, service registry, orchestration,
    and request handling.
    """

    def __init__(
        self,
        orchestrator_type: OrchestratorType = OrchestratorType.SLURM,
        recipe_directory: str = "recipes",
    ):
        """
        Initialize ServerManager

        Args:
            orchestrator_type: Type of orchestrator to use (SLURM or K8S)
            recipe_directory: Directory containing service recipes
        """
        logger.info("Initializing ServerManager")

        # Initialize components
        self.recipe_loader = RecipeLoader(recipe_directory=recipe_directory)
        self.service_registry = ServiceRegistry()

        # Initialize orchestrator
        if orchestrator_type == OrchestratorType.SLURM:
            self.orchestrator = SlurmOrchestrator()
            logger.info("Using SLURM orchestrator")
        elif orchestrator_type == OrchestratorType.K8S:
            # TODO: Implement K8S orchestrator
            raise NotImplementedError("K8S orchestrator not yet implemented")
        else:
            raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")

        logger.info("ServerManager initialization complete")

    def start_service(
        self, recipe_name: str, config: Optional[Dict] = None
    ) -> ServiceInstance:
        """
        Start a service from a recipe

        Args:
            recipe_name: Name of the service recipe
            config: Optional configuration overrides

        Returns:
            ServiceInstance for the started service

        Raises:
            FileNotFoundError: If recipe not found
            ValueError: If recipe validation fails
            RuntimeError: If service deployment fails
        """
        logger.info(f"Starting service from recipe: {recipe_name}")

        # Load recipe
        try:
            recipe = self.recipe_loader.load_recipe(recipe_name)
        except FileNotFoundError as e:
            logger.error(f"Recipe not found: {recipe_name}")
            raise
        except ValueError as e:
            logger.error(f"Recipe validation failed: {e}")
            raise

        # Apply config overrides if provided
        if config:
            logger.debug(f"Applying config overrides: {config}")
            # TODO: Implement config merging logic
            pass

        # Deploy service using orchestrator
        try:
            orchestrator_handle = self.orchestrator.deploy_service(recipe)
            logger.info(f"Service deployed with handle: {orchestrator_handle}")
        except Exception as e:
            logger.error(f"Failed to deploy service: {e}")
            raise RuntimeError(f"Service deployment failed: {e}")

        # Create service instance
        instance = ServiceInstance(
            recipe=recipe,
            orchestrator_handle=orchestrator_handle,
            status=ServiceStatus.STARTING,
        )

        # Register service
        if not self.service_registry.register_service(instance):
            logger.error(f"Failed to register service: {instance.id}")
            # Attempt cleanup
            try:
                self.orchestrator.stop_service(orchestrator_handle)
            except Exception:
                pass
            raise RuntimeError("Service registration failed")

        # Update status to running (simplified - in reality, wait for health check)
        instance.update_status(ServiceStatus.RUNNING)

        logger.info(f"Service started successfully: {instance.id} ({recipe.name})")
        return instance

    def stop_service(self, service_id: str) -> bool:
        """
        Stop a running service

        Args:
            service_id: ID of the service to stop

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Stopping service: {service_id}")

        # Get service instance
        instance = self.service_registry.get_service(service_id)
        if not instance:
            logger.error(f"Service not found: {service_id}")
            return False

        # Update status
        instance.update_status(ServiceStatus.STOPPING)

        # Stop via orchestrator
        try:
            success = self.orchestrator.stop_service(instance.orchestrator_handle)
            if not success:
                logger.error(f"Orchestrator failed to stop service: {service_id}")
                instance.update_status(ServiceStatus.ERROR)
                return False
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            instance.update_status(ServiceStatus.ERROR)
            return False

        # Update status and unregister
        instance.update_status(ServiceStatus.STOPPED)
        self.service_registry.unregister_service(service_id)

        logger.info(f"Service stopped successfully: {service_id}")
        return True

    def list_available_services(self) -> List[str]:
        """
        List available service recipes

        Returns:
            List of available recipe names
        """
        logger.info("Listing available services")
        recipes = self.recipe_loader.list_available_recipes()
        logger.debug(f"Found {len(recipes)} available recipes")
        return recipes

    def list_running_services(self) -> List[Dict]:
        """
        List running service instances

        Returns:
            List of running service information as dictionaries
        """
        logger.info("Listing running services")
        instances = self.service_registry.get_all_services()

        return [instance.to_dict() for instance in instances]

    def get_service_status(self, service_id: str) -> Dict:
        """
        Get status of a service

        Args:
            service_id: ID of the service

        Returns:
            Service status information as dictionary

        Raises:
            ValueError: If service not found
        """
        logger.info(f"Getting status for service: {service_id}")

        instance = self.service_registry.get_service(service_id)
        if not instance:
            logger.error(f"Service not found: {service_id}")
            raise ValueError(f"Service not found: {service_id}")

        # Get orchestrator status
        try:
            orch_status = self.orchestrator.get_service_status(
                instance.orchestrator_handle
            )
            logger.debug(f"Orchestrator status for {service_id}: {orch_status}")
        except Exception as e:
            logger.warning(f"Failed to get orchestrator status: {e}")
            orch_status = ServiceStatus.UNKNOWN

        # Update instance status if needed
        if orch_status != instance.status:
            instance.update_status(orch_status)

        return instance.to_dict()

    def check_service_health(self, service_id: str) -> bool:
        """
        Check if a service is healthy

        Args:
            service_id: ID of the service

        Returns:
            True if healthy, False otherwise
        """
        logger.debug(f"Checking health for service: {service_id}")

        instance = self.service_registry.get_service(service_id)
        if not instance:
            return False

        return instance.is_healthy()

    def get_service_logs(self, service_id: str) -> str:
        """
        Get logs for a service

        Args:
            service_id: ID of the service

        Returns:
            Service logs as string

        Raises:
            ValueError: If service not found
        """
        logger.info(f"Getting logs for service: {service_id}")

        instance = self.service_registry.get_service(service_id)
        if not instance:
            raise ValueError(f"Service not found: {service_id}")

        try:
            logs = self.orchestrator.get_service_logs(instance.orchestrator_handle)
            return logs
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return f"Error retrieving logs: {e}"

    def cleanup_stale_services(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale services

        Args:
            max_age_hours: Maximum age in hours before considering service stale

        Returns:
            Number of services cleaned up
        """
        logger.info(f"Cleaning up stale services (max age: {max_age_hours}h)")
        count = self.service_registry.cleanup_stale_services(max_age_hours)
        return count

    def get_recipe_info(self, recipe_name: str) -> Dict:
        """
        Get information about a recipe without loading it

        Args:
            recipe_name: Name of the recipe

        Returns:
            Recipe information dictionary
        """
        return self.recipe_loader.get_recipe_info(recipe_name)

    def create_recipe_template(self, recipe_name: str) -> Path:
        """
        Create a new recipe template

        Args:
            recipe_name: Name for the new recipe

        Returns:
            Path to created template file
        """
        logger.info(f"Creating recipe template: {recipe_name}")
        return self.recipe_loader.create_recipe_template(recipe_name)

    def get_statistics(self) -> Dict:
        """
        Get overall statistics

        Returns:
            Dictionary with statistics
        """
        instances = self.service_registry.get_all_services()

        status_counts = {}
        for status in ServiceStatus:
            count = len(self.service_registry.get_services_by_status(status))
            status_counts[status.value] = count

        return {
            "total_services": len(instances),
            "status_breakdown": status_counts,
            "available_recipes": len(self.list_available_services()),
        }

    def shutdown(self) -> None:
        """Shutdown the server manager and stop all services"""
        logger.warning("Shutting down ServerManager")

        instances = self.service_registry.get_all_services()
        for instance in instances:
            try:
                self.stop_service(instance.id)
            except Exception as e:
                logger.error(f"Error stopping service {instance.id}: {e}")

        logger.info("ServerManager shutdown complete")
