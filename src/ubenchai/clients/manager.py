"""
ClientManager - Central orchestration for benchmarking clients
"""

from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from ubenchai.clients.runs import ClientRun, RunRegistry, RunStatus
from ubenchai.clients.recipes import ClientRecipe
from ubenchai.clients.recipe_loader import ClientRecipeLoader


class ClientManager:
    """
    Central orchestration component for managing benchmarking clients.

    Coordinates recipe loading, run tracking, orchestration, and health validation.
    Provides CLI commands for start/stop/list/status.
    """

    def __init__(self, recipe_directory: str = "recipes/clients"):
        """
        Initialize ClientManager

        Args:
            recipe_directory: Directory containing client recipes
        """
        logger.info("Initializing ClientManager")

        # Initialize components
        self.recipe_loader = ClientRecipeLoader(recipe_directory=recipe_directory)
        self.run_registry = RunRegistry()

        # ✅ LAZY LOADING: Initialize these only when needed
        self._health_resolver = None
        self._orchestrator = None

        logger.info("ClientManager initialization complete")

    @property
    def health_resolver(self):
        """
        Lazy-load health resolver only when needed.
        This allows read-only commands to work without external dependencies.
        """
        if self._health_resolver is None:
            logger.debug("Initializing HealthResolver (lazy loading)")
            from ubenchai.clients.health_resolver import HealthResolver

            self._health_resolver = HealthResolver()
        return self._health_resolver

    @property
    def orchestrator(self):
        """
        Lazy-load orchestrator only when needed.

        This allows commands like 'client list' to work in local environment
        without requiring SLURM configuration.
        """
        if self._orchestrator is None:
            logger.debug("Initializing ClientOrchestrator (lazy loading)")
            from ubenchai.clients.client_orchestrator import ClientOrchestrator

            self._orchestrator = ClientOrchestrator()
        return self._orchestrator

    def start_client(
        self, recipe_name: str, overrides: Optional[Dict] = None
    ) -> ClientRun:
        """
        Start a benchmarking client from a recipe

        Args:
            recipe_name: Name of the client recipe
            overrides: Optional configuration overrides

        Returns:
            ClientRun instance

        Raises:
            FileNotFoundError: If recipe not found
            ValueError: If recipe validation or endpoint resolution fails
            RuntimeError: If client deployment fails
        """
        logger.info(f"Starting client from recipe: {recipe_name}")

        # Load recipe
        try:
            recipe = self.recipe_loader.load_recipe(recipe_name)
        except FileNotFoundError:
            logger.error(f"Recipe not found: {recipe_name}")
            raise
        except ValueError as e:
            logger.error(f"Recipe validation failed: {e}")
            raise

        # Apply overrides if provided
        if overrides:
            logger.debug(f"Applying overrides: {overrides}")
            # TODO: Implement override merging logic

        # Resolve target endpoint
        try:
            resolved_target = self.health_resolver.resolve_endpoint(recipe)
            logger.info(f"Resolved target endpoint: {resolved_target.endpoint}")
        except ValueError as e:
            logger.error(f"Failed to resolve endpoint: {e}")
            raise

        # Check connectivity
        if not self.health_resolver.check_connectivity(resolved_target):
            raise RuntimeError(
                f"Target endpoint not reachable: {resolved_target.endpoint}"
            )

        logger.debug(
            f"About to create temporary run with recipe_name={recipe.name}, orchestrator_handle='pending', target_endpoint={resolved_target.endpoint}"
        )

        # Deploy via orchestrator FIRST to get the job ID
        # We need to create a temporary run just to pass to the orchestrator
        try:
            temp_run = ClientRun(
                recipe_name=recipe.name,
                orchestrator_handle="pending",  # Temporary placeholder
                target_endpoint=resolved_target.endpoint,
            )
            logger.debug(f"Temporary run created successfully: {temp_run.id}")
        except ValueError as e:
            logger.error(f"Failed to create temporary run: {e}", exc_info=True)
            raise

        logger.debug("About to call orchestrator.submit()")
        try:
            job_id = self.orchestrator.submit(
                temp_run, recipe, resolved_target.endpoint
            )
            logger.info(f"Client deployed with job ID: {job_id}")
        except Exception as e:
            logger.error(f"Failed to deploy client: {e}", exc_info=True)
            raise RuntimeError(f"Client deployment failed: {e}")

        logger.debug(f"About to create final run with job_id={job_id}")
        # NOW create the real run instance with the valid orchestrator_handle
        try:
            run = ClientRun(
                recipe_name=recipe.name,
                orchestrator_handle=job_id,  # Use the job ID from deployment
                target_endpoint=resolved_target.endpoint,
            )
            logger.debug(f"Final run created successfully: {run.id}")
        except ValueError as e:
            logger.error(f"Failed to create final run: {e}", exc_info=True)
            raise

        # Preserve the ID from the temporary run
        run.id = temp_run.id

        # Register run
        if not self.run_registry.register(run):
            logger.error(f"Failed to register run: {run.id}")
            # Attempt cleanup
            try:
                self.orchestrator.stop(job_id)
            except Exception:
                pass
            raise RuntimeError("Run registration failed")

        # Update status
        run.update_status(RunStatus.RUNNING)

        logger.info(f"Client started successfully: {run.id} ({recipe.name})")
        return run

    def stop_client(self, run_id: str) -> bool:
        """
        Stop a running client

        Args:
            run_id: ID of the run to stop

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Stopping client run: {run_id}")

        # Get run instance
        run = self.run_registry.get(run_id)
        if not run:
            logger.error(f"Run not found: {run_id}")
            return False

        # Update status
        run.update_status(RunStatus.CANCELED)

        # Stop via orchestrator (only if initialized)
        if self._orchestrator is not None:
            try:
                success = self.orchestrator.stop(run.orchestrator_handle)
                if not success:
                    logger.error(f"Orchestrator failed to stop run: {run_id}")
                    run.update_status(RunStatus.FAILED)
                    return False
            except Exception as e:
                logger.error(f"Error stopping run: {e}")
                run.update_status(RunStatus.FAILED)
                return False

        logger.info(f"Client run stopped successfully: {run_id}")
        return True

    def list_available_clients(self) -> List[str]:
        """
        List available client recipes

        Returns:
            List of available recipe names
        """
        logger.info("Listing available client recipes")
        recipes = self.recipe_loader.list_available_recipes()
        logger.debug(f"Found {len(recipes)} available recipes")
        return recipes

    def list_running_clients(self) -> List[Dict]:
        """
        List running client instances

        Returns:
            List of running client information as dictionaries
        """
        logger.info("Listing running clients")
        runs = self.run_registry.get_all()
        return [run.to_dict() for run in runs]

    def get_client_status(self, run_id: str) -> Dict:
        """
        Get status of a client run

        Args:
            run_id: ID of the run

        Returns:
            Run status information as dictionary

        Raises:
            ValueError: If run not found
        """
        logger.info(f"Getting status for run: {run_id}")

        run = self.run_registry.get(run_id)
        if not run:
            logger.error(f"Run not found: {run_id}")
            raise ValueError(f"Run not found: {run_id}")

        # Get orchestrator status (only if orchestrator was initialized)
        if self._orchestrator is not None:
            try:
                orch_status = self.orchestrator.status(run.orchestrator_handle)
                logger.debug(f"Orchestrator status for {run_id}: {orch_status}")

                # Update run status if different
                if orch_status != run.status:
                    run.update_status(orch_status)

            except Exception as e:
                logger.warning(f"Failed to get orchestrator status: {e}")

        return run.to_dict()

    def validate_recipe(self, recipe_name: str) -> Dict:
        """
        Validate a recipe without running it

        Args:
            recipe_name: Name of the recipe

        Returns:
            Validation report dictionary
        """
        logger.info(f"Validating recipe: {recipe_name}")

        try:
            recipe = self.recipe_loader.load_recipe(recipe_name)
            errors = self.recipe_loader.validate_recipe(recipe)

            return {
                "recipe_name": recipe_name,
                "valid": len(errors) == 0,
                "errors": errors,
            }

        except Exception as e:
            return {
                "recipe_name": recipe_name,
                "valid": False,
                "errors": [str(e)],
            }

    def get_client_logs(self, run_id: str) -> str:
        """
        Get logs for a client run

        Args:
            run_id: ID of the run

        Returns:
            Run logs as string
        """
        logger.info(f"Getting logs for run: {run_id}")

        run = self.run_registry.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        # Only try to get logs if orchestrator is available
        if self._orchestrator is not None:
            try:
                logs = self.orchestrator.stdout(run.orchestrator_handle)
                return logs
            except Exception as e:
                logger.error(f"Failed to get logs: {e}")
                return f"Error retrieving logs: {e}"
        else:
            return "Orchestrator not initialized - logs not available"

    def cleanup_stale_runs(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale runs

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of runs cleaned up
        """
        logger.info(f"Cleaning up stale runs (max age: {max_age_hours}h)")
        count = self.run_registry.cleanup_stale_runs(max_age_hours)
        return count

    def get_recipe_info(self, recipe_name: str) -> Dict:
        """
        Get information about a recipe

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
        runs = self.run_registry.get_all()

        status_counts = {}
        for status in RunStatus:
            count = len(self.run_registry.get_runs_by_status(status))
            status_counts[status.value] = count

        return {
            "total_runs": len(runs),
            "status_breakdown": status_counts,
            "available_recipes": len(self.list_available_clients()),
        }

    def shutdown(self) -> None:
        """Shutdown the client manager"""
        logger.warning("Shutting down ClientManager")
        # Cleanup is automatic due to persistence
        logger.info("ClientManager shutdown complete")
