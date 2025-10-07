"""
Orchestrator - Abstract base class for service orchestrators
"""

from enum import Enum
from abc import ABC, abstractmethod
from typing import Optional

from ubenchai.servers.services import ServiceRecipe, ServiceStatus


class OrchestratorType(Enum):
    """Supported orchestrator types"""

    SLURM = "slurm"
    K8S = "kubernetes"


class Orchestrator(ABC):
    """
    Abstract base class for service orchestrators.

    Orchestrators manage the deployment, lifecycle, and monitoring
    of containerized services on different platforms (SLURM, K8s, etc.)
    """

    @abstractmethod
    def deploy_service(self, recipe: ServiceRecipe) -> str:
        """
        Deploy a service from a recipe

        Args:
            recipe: ServiceRecipe containing deployment specification

        Returns:
            Orchestrator-specific handle (job ID, deployment name, etc.)

        Raises:
            RuntimeError: If deployment fails
        """

    @abstractmethod
    def stop_service(self, handle: str) -> bool:
        """
        Stop a running service

        Args:
            handle: Orchestrator handle from deploy_service

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def get_service_status(self, handle: str) -> ServiceStatus:
        """
        Get the current status of a service

        Args:
            handle: Orchestrator handle from deploy_service

        Returns:
            ServiceStatus enumeration value
        """

    @abstractmethod
    def get_service_logs(self, handle: str) -> str:
        """
        Get logs from a service

        Args:
            handle: Orchestrator handle from deploy_service

        Returns:
            Log output as string
        """

    @abstractmethod
    def scale_service(self, handle: str, replicas: int) -> bool:
        """
        Scale a service to specified number of replicas

        Args:
            handle: Orchestrator handle from deploy_service
            replicas: Desired number of replicas

        Returns:
            True if successful, False otherwise
        """

    def check_connection(self) -> bool:
        """
        Check if orchestrator is available and accessible

        Returns:
            True if orchestrator is available, False otherwise
        """
        return True

    def health_check(self, handle: str) -> bool:
        """
        Perform health check on a service

        Args:
            handle: Orchestrator handle from deploy_service

        Returns:
            True if service is healthy, False otherwise
        """
        status = self.get_service_status(handle)
        return status == ServiceStatus.RUNNING
