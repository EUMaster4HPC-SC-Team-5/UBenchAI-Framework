"""
Unit tests for ServerManager
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import yaml

from ubenchai.servers.manager import ServerManager
from ubenchai.servers.orchestrator import OrchestratorType
from ubenchai.servers.services import (
    ServiceRecipe,
    ServiceInstance,
    ServiceStatus,
    ResourceSpec,
)


class TestServerManager:
    """Tests for ServerManager"""

    @pytest.fixture
    def temp_recipe_dir(self, tmp_path):
        """Fixture providing temporary recipe directory"""
        recipe_dir = tmp_path / "recipes"
        recipe_dir.mkdir()
        return recipe_dir

    @pytest.fixture
    def mock_orchestrator(self):
        """Fixture providing mock orchestrator"""
        mock = Mock()
        mock.deploy_service.return_value = "job-123"
        mock.stop_service.return_value = True
        mock.get_service_status.return_value = ServiceStatus.RUNNING
        mock.get_service_logs.return_value = "Mock logs"
        return mock

    @pytest.fixture
    def manager_with_mock(self, temp_recipe_dir, mock_orchestrator):
        """Fixture providing ServerManager with mocked orchestrator"""
        with patch(
            "ubenchai.servers.manager.SlurmOrchestrator",
            return_value=mock_orchestrator,
        ):
            manager = ServerManager(
                orchestrator_type=OrchestratorType.SLURM,
                recipe_directory=str(temp_recipe_dir),
            )
            manager.orchestrator = mock_orchestrator
            return manager

    @pytest.fixture
    def valid_recipe_data(self):
        """Fixture providing valid recipe data"""
        return {
            "name": "test-service",
            "image": "docker://test/image:latest",
            "resources": {
                "cpu_cores": 2,
                "memory_gb": 4,
                "gpu_count": 0,
            },
        }

    def create_recipe_file(self, directory, name, data):
        """Helper to create recipe YAML file"""
        recipe_path = directory / f"{name}.yml"
        with open(recipe_path, "w") as f:
            yaml.dump(data, f)
        return recipe_path

    def test_initialization_slurm(self, temp_recipe_dir):
        """Test ServerManager initialization with SLURM"""
        with patch("ubenchai.servers.manager.SlurmOrchestrator"):
            manager = ServerManager(
                orchestrator_type=OrchestratorType.SLURM,
                recipe_directory=str(temp_recipe_dir),
            )
            assert manager.recipe_loader is not None
            assert manager.service_registry is not None

    def test_initialization_k8s_not_implemented(self, temp_recipe_dir):
        """Test K8S orchestrator raises NotImplementedError"""
        with pytest.raises(NotImplementedError, match="K8S orchestrator not yet"):
            ServerManager(
                orchestrator_type=OrchestratorType.K8S,
                recipe_directory=str(temp_recipe_dir),
            )

    def test_start_service_success(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data, mock_orchestrator
    ):
        """Test successfully starting a service"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)

        instance = manager_with_mock.start_service("test-service")

        assert instance is not None
        assert instance.recipe.name == "test-service"
        assert instance.orchestrator_handle == "job-123"
        mock_orchestrator.deploy_service.assert_called_once()

    def test_start_service_recipe_not_found(self, manager_with_mock):
        """Test starting service with non-existent recipe"""
        with pytest.raises(FileNotFoundError):
            manager_with_mock.start_service("nonexistent")

    def test_start_service_deployment_failure(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data, mock_orchestrator
    ):
        """Test service start when deployment fails"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)
        mock_orchestrator.deploy_service.side_effect = Exception("Deployment failed")

        with pytest.raises(RuntimeError, match="Service deployment failed"):
            manager_with_mock.start_service("test-service")

    def test_stop_service_success(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data, mock_orchestrator
    ):
        """Test successfully stopping a service"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)

        # Start service first
        instance = manager_with_mock.start_service("test-service")

        # Stop service
        result = manager_with_mock.stop_service(instance.id)

        assert result is True
        mock_orchestrator.stop_service.assert_called()

    def test_stop_service_by_job_id(self, manager_with_mock, mock_orchestrator):
        """Test stopping service by job ID"""
        with patch("subprocess.run") as mock_run:
            # Mock squeue to show job exists
            mock_run.return_value = Mock(returncode=0, stdout="test-job\n", stderr="")

            result = manager_with_mock.stop_service("12345")

            assert result is True
            mock_orchestrator.stop_service.assert_called_with("12345")

    def test_stop_service_not_found(self, manager_with_mock):
        """Test stopping non-existent service"""
        with patch("subprocess.run") as mock_run:
            # Mock squeue to show job doesn't exist
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="")

            result = manager_with_mock.stop_service("nonexistent")

            assert result is False

    def test_list_available_services(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data
    ):
        """Test listing available services"""
        self.create_recipe_file(temp_recipe_dir, "service1", valid_recipe_data)
        self.create_recipe_file(temp_recipe_dir, "service2", valid_recipe_data)

        services = manager_with_mock.list_available_services()

        assert len(services) == 2
        assert "service1" in services
        assert "service2" in services

    def test_list_running_services(self, manager_with_mock):
        """Test listing running services from SLURM"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="12345|test-service|RUNNING|2025-10-13T10:00:00\n",
                stderr="",
            )

            services = manager_with_mock.list_running_services()

            assert len(services) == 1
            assert services[0]["id"] == "12345"
            assert services[0]["recipe_name"] == "test-service"
            assert services[0]["status"] == "running"

    def test_get_service_status_success(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data, mock_orchestrator
    ):
        """Test getting service status"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)
        instance = manager_with_mock.start_service("test-service")

        status = manager_with_mock.get_service_status(instance.id)

        assert status["id"] == instance.id
        assert status["recipe_name"] == "test-service"
        assert "status" in status

    def test_get_service_status_not_found(self, manager_with_mock):
        """Test getting status for non-existent service"""
        with pytest.raises(ValueError, match="Service not found"):
            manager_with_mock.get_service_status("nonexistent")

    def test_check_service_health(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data
    ):
        """Test checking service health"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)
        instance = manager_with_mock.start_service("test-service")

        # Service should be healthy (RUNNING status)
        result = manager_with_mock.check_service_health(instance.id)
        assert result is True

    def test_check_service_health_not_found(self, manager_with_mock):
        """Test health check for non-existent service"""
        result = manager_with_mock.check_service_health("nonexistent")
        assert result is False

    def test_get_service_logs(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data, mock_orchestrator
    ):
        """Test getting service logs"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)
        instance = manager_with_mock.start_service("test-service")

        logs = manager_with_mock.get_service_logs(instance.id)

        assert logs == "Mock logs"
        mock_orchestrator.get_service_logs.assert_called()

    def test_get_service_logs_not_found(self, manager_with_mock):
        """Test getting logs for non-existent service"""
        with pytest.raises(ValueError, match="Service not found"):
            manager_with_mock.get_service_logs("nonexistent")

    def test_cleanup_stale_services(self, manager_with_mock):
        """Test cleaning up stale services"""
        count = manager_with_mock.cleanup_stale_services(max_age_hours=24)
        assert count >= 0

    def test_get_recipe_info(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data
    ):
        """Test getting recipe information"""
        valid_recipe_data["description"] = "Test description"
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)

        info = manager_with_mock.get_recipe_info("test-service")

        assert info["name"] == "test-service"
        assert "description" in info

    def test_create_recipe_template(self, manager_with_mock):
        """Test creating a recipe template"""
        template_path = manager_with_mock.create_recipe_template("new-recipe")

        assert template_path.exists()
        assert "new-recipe" in str(template_path)

    def test_get_statistics(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data
    ):
        """Test getting statistics"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)
        manager_with_mock.start_service("test-service")

        stats = manager_with_mock.get_statistics()

        assert "total_services" in stats
        assert "status_breakdown" in stats
        assert "available_recipes" in stats
        assert stats["total_services"] >= 1

    def test_shutdown(
        self, manager_with_mock, temp_recipe_dir, valid_recipe_data, mock_orchestrator
    ):
        """Test shutting down manager"""
        self.create_recipe_file(temp_recipe_dir, "test-service", valid_recipe_data)
        manager_with_mock.start_service("test-service")

        manager_with_mock.shutdown()

        # Verify stop was called
        mock_orchestrator.stop_service.assert_called()
